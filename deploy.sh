#!/bin/bash
set -e

# Configuration
STACK_NAME="teleport-prod-muddys-top-10"
STACK_NAME_OVERRIDDEN=false
DEPLOY_ENV="default"
DEPLOY_REGION="us-west-2"
USE_CONTAINER_BUILD=true
SAM_CAPABILITIES="CAPABILITY_IAM CAPABILITY_NAMED_IAM"
FORCE_AGENTCORE_RUNTIME_UPDATE=false
AGENTCORE_MEMORY_NAME_OVERRIDE=""
AGENTCORE_RUNTIME_NAME_OVERRIDE=""
CAMPAIGN_MODEL_ID_OVERRIDE=""
CAMPAIGN_MODEL_ENDPOINT_OVERRIDE=""
CAMPAIGN_MODEL_RESOURCE_ARN_OVERRIDE=""
CAMPAIGN_MODEL_API_KEY_SECRET_ARN_OVERRIDE=""
CAMPAIGN_IMAGE_MODEL_ID_OVERRIDE=""
CAMPAIGN_IMAGE_MODEL_API_KEY_SECRET_ARN_OVERRIDE=""
CAMPAIGN_IMAGE_SIZE_OVERRIDE=""
ENABLE_SPOTIFY_VALIDATION_OVERRIDE=""
ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE=""
LAMBDA_ARCHITECTURE_OVERRIDE=""
FRONTEND_DIR="frontend"
FRONTEND_SOURCE="$FRONTEND_DIR/index.html"
FRONTEND_BUILD="$FRONTEND_DIR/index-configured.html"
ADMIN_SOURCE="$FRONTEND_DIR/admin.html"
ADMIN_BUILD="$FRONTEND_DIR/admin-configured.html"
DATA_VIEWER_SOURCE="$FRONTEND_DIR/data-viewer.html"
DATA_VIEWER_BUILD="$FRONTEND_DIR/data-viewer-configured.html"

usage() {
    cat <<EOF
Usage: ./deploy.sh [options]

Build and deploy Muddy's Music Cafe Top 10 Tracker, configure the frontend,
upload it to the private S3 bucket, and invalidate CloudFront.

Missing environments are configured by this script and saved to samconfig.toml.

Options:
  -h, --help, -help          Show this help and exit
  --env NAME                 SAM config environment to deploy (default: $DEPLOY_ENV)
  --stack-name NAME          CloudFormation/SAM stack name (default: $STACK_NAME)
  --agentcore-memory-name NAME
                              AgentCore Memory name; must be unique in the account/region
  --agentcore-runtime-name NAME
                              AgentCore Runtime name; must be unique in the account/region
  --campaign-model-id ID     Bedrock model ID for campaign generation
  --campaign-model-endpoint NAME
                              Model endpoint family: bedrock-mantle, bedrock-runtime, or strands-openai-responses
  --campaign-model-arn ARN   IAM resource ARN for bedrock-runtime models
  --campaign-model-api-key-secret-arn ARN
                              Secrets Manager ARN containing Bedrock/Mantle API key for Strands OpenAI Responses
  --clear-campaign-model     Clear campaign model settings and use deterministic drafts
  --campaign-image-model-id ID
                              Optional OpenAI Responses compatible image-generation model for final infographic PNGs
  --campaign-image-model-api-key-secret-arn ARN
                              Optional image model API key secret; blank reuses campaign model API key secret
  --campaign-image-size SIZE  Requested image size for direct model PNG generation (default: 1280x720)
  --clear-campaign-image-model
                              Clear direct model PNG generation settings and use Playwright rendering
  --enable-spotify           Alias for --enable-spotify-playlists
  --disable-spotify          Alias for --disable-spotify-playlists
  --enable-spotify-validation
                              Enable Spotify as a track validation source
  --disable-spotify-validation
                              Disable Spotify as a track validation source
  --enable-spotify-playlists Enable Spotify OAuth UI and playlist generation
  --disable-spotify-playlists
                              Disable Spotify OAuth UI and playlist generation
  --lambda-arch ARCH         Lambda architecture: x86_64 or arm64
  --arm64                    Shortcut for --lambda-arch arm64
  --x86-64                   Shortcut for --lambda-arch x86_64
  --no-container-build       Use local Python build instead of Docker/SAM container build
  --force-agentcore-runtime-update
                              Upload AgentCore Runtime to a unique S3 key so CloudFormation updates the runtime

Prerequisites:
  - AWS CLI configured for the target account and region
  - SAM CLI installed
  - Docker available for the default containerized SAM build
  - python3 with pip available for AgentCore Runtime Linux ARM64 packaging
  - python3.14 available on PATH only when using --no-container-build
EOF
}

config_env_exists() {
    [ -f "samconfig.toml" ] && grep -q "^\[$1\.deploy\.parameters\]" samconfig.toml
}

samconfig_value() {
    local env_name="$1"
    local key="$2"

    [ -f "samconfig.toml" ] || return 0

    awk -v section="[$env_name.deploy.parameters]" -v key="$key" '
        $0 == section { in_section = 1; next }
        /^\[/ { in_section = 0 }
        in_section && $1 == key {
            sub(/^[^=]*= */, "", $0)
            gsub(/^"|"$/, "", $0)
            print $0
            exit
        }
    ' samconfig.toml
}

samconfig_parameter_override_value() {
    local env_name="$1"
    local key="$2"
    python3 - "$env_name" "$key" <<'PY'
import shlex
import sys
from pathlib import Path

env_name, key = sys.argv[1:3]
path = Path("samconfig.toml")
if not path.exists():
    raise SystemExit(0)

section = f"[{env_name}.deploy.parameters]"
in_section = False
raw_value = ""
for line in path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if stripped == section:
        in_section = True
        continue
    if stripped.startswith("[") and stripped.endswith("]"):
        in_section = False
    if in_section and stripped.startswith("parameter_overrides"):
        raw_value = stripped.split("=", 1)[1].strip()
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == '"':
            raw_value = bytes(raw_value[1:-1], "utf-8").decode("unicode_escape")
        break

try:
    tokens = shlex.split(raw_value)
except ValueError:
    tokens = raw_value.split()

for token in tokens:
    if token.startswith(f"{key}="):
        print(token.split("=", 1)[1])
        break
PY
}

set_samconfig_parameter_override() {
    local env_name="$1"
    local key="$2"
    local value="$3"
    python3 - "$env_name" "$key" "$value" <<'PY'
import re
import shlex
import sys
from pathlib import Path

env_name, key, value = sys.argv[1:4]
path = Path("samconfig.toml")
lines = path.read_text(encoding="utf-8").splitlines()
section = f"[{env_name}.deploy.parameters]"


def decode_toml_string(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return bytes(raw[1:-1], "utf-8").decode("unicode_escape")
    return raw


def encode_toml_string(raw):
    return raw.replace("\\", "\\\\").replace('"', '\\"')


def parse_parameter_overrides(raw):
    if not raw:
        return []
    try:
        return shlex.split(raw)
    except ValueError:
        # Fall back to whitespace splitting for partially broken existing lines.
        return raw.split()


in_section = False
param_line_index = None
insert_index = None
current_value = ""

for index, line in enumerate(lines):
    stripped = line.strip()
    if stripped == section:
        in_section = True
        insert_index = index + 1
        continue
    if stripped.startswith("[") and stripped.endswith("]"):
        if in_section:
            insert_index = index
            break
        in_section = False
    if in_section:
        insert_index = index + 1
        if re.match(r"^parameter_overrides\s*=", stripped):
            param_line_index = index
            current_value = decode_toml_string(stripped.split("=", 1)[1])

if insert_index is None:
    raise SystemExit(f"Missing samconfig section: {section}")

tokens = [
    token for token in parse_parameter_overrides(current_value)
    if not token.startswith(f"{key}=")
]
if value:
    tokens.append(f"{key}={value}")
replacement = f'parameter_overrides = "{encode_toml_string(" ".join(tokens))}"'

if param_line_index is None:
    lines.insert(insert_index, replacement)
else:
    lines[param_line_index] = replacement

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

prompt_with_default() {
    local prompt_text="$1"
    local default_value="$2"
    local value

    read -r -p "$prompt_text [$default_value]: " value
    echo "${value:-$default_value}"
}

prompt_secret_optional() {
    local prompt_text="$1"
    local value

    read -r -s -p "$prompt_text (leave blank to skip): " value
    echo "" >&2
    echo "$value"
}

prompt_yes_no() {
    local prompt_text="$1"
    local default_value="$2"
    local value

    read -r -p "$prompt_text [$default_value]: " value
    value="${value:-$default_value}"
    case "$value" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
}

resource_env_name() {
    local env_name="$1"
    if [ "$env_name" = "default" ]; then
        printf '%s' "prod"
        return
    fi
    printf '%s' "$env_name" | sed 's/^teleport-//'
}

resource_name_default() {
    local env_name="$1"
    local resource="$2"
    printf 'teleport-%s-%s' "$(resource_env_name "$env_name")" "$resource"
}

agentcore_memory_name_default() {
    local env_name="$1"
    local sanitized

    sanitized=$(resource_name_default "$env_name" "agentcore-memory" | tr '-' '_' | cut -c1-48)
    if ! printf '%s' "$sanitized" | grep -Eq '^[A-Za-z]'; then
        sanitized="teleport_${sanitized}"
        sanitized=$(printf '%s' "$sanitized" | cut -c1-48)
    fi
    printf '%s' "$sanitized"
}

agentcore_runtime_name_default() {
    local env_name="$1"
    local sanitized

    sanitized=$(resource_name_default "$env_name" "campaign-agent" | tr '-' '_' | cut -c1-48)
    if ! printf '%s' "$sanitized" | grep -Eq '^[A-Za-z]'; then
        sanitized="teleport_${sanitized}"
        sanitized=$(printf '%s' "$sanitized" | cut -c1-48)
    fi
    printf '%s' "$sanitized"
}

toml_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s' "$value"
}

package_agentcore_runtime() {
    local account_id
    local bucket_name
    local artifact_key
    local artifact_path
    local artifact_build_dir
    local runtime_name

    runtime_name="$(samconfig_parameter_override_value "$DEPLOY_ENV" "AgentCoreRuntimeName")"
    if [ -z "$runtime_name" ]; then
        runtime_name="$(agentcore_runtime_name_default "$DEPLOY_ENV")"
        set_samconfig_parameter_override "$DEPLOY_ENV" "AgentCoreRuntimeName" "$runtime_name"
    fi

    account_id=$(aws sts get-caller-identity --query Account --output text)
    bucket_name="teleport-$(resource_env_name "$DEPLOY_ENV")-agentcore-artifacts-$account_id-$DEPLOY_REGION"
    if [ "$FORCE_AGENTCORE_RUNTIME_UPDATE" = true ]; then
        artifact_key="$STACK_NAME/agentcore-runtime/deployment-$(date -u +%Y%m%dT%H%M%SZ).zip"
    else
        artifact_key="$STACK_NAME/agentcore-runtime/deployment.zip"
    fi
    artifact_path="/tmp/$STACK_NAME-agentcore-runtime.zip"
    artifact_build_dir="/tmp/$STACK_NAME-agentcore-runtime-build"

    rm -rf "$artifact_build_dir"
    mkdir -p "$artifact_build_dir"

    if [ -s "src/agentcore-runtime/requirements.txt" ]; then
        python3 -m pip install \
            --target "$artifact_build_dir" \
            --requirement "src/agentcore-runtime/requirements.txt" \
            --platform manylinux2014_aarch64 \
            --implementation cp \
            --python-version 3.14 \
            --abi cp314 \
            --only-binary=:all: \
            --upgrade \
            --quiet
    fi

    cp -R src/agentcore-runtime/. "$artifact_build_dir"/
    find "$artifact_build_dir" -type d -name "__pycache__" -prune -exec rm -rf {} +
    find "$artifact_build_dir" -type f -name "*.pyc" -delete

    python3 - "$artifact_path" "$artifact_build_dir" <<'PY'
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

output = Path(sys.argv[1])
source = Path(sys.argv[2])
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in source.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(source).as_posix())
PY

    if ! aws s3api head-bucket --bucket "$bucket_name" >/dev/null 2>&1; then
        if [ "$DEPLOY_REGION" = "us-east-1" ]; then
            aws s3api create-bucket --bucket "$bucket_name" >/dev/null
        else
            aws s3api create-bucket \
                --bucket "$bucket_name" \
                --create-bucket-configuration "LocationConstraint=$DEPLOY_REGION" >/dev/null
        fi
    fi

    aws s3 cp "$artifact_path" "s3://$bucket_name/$artifact_key" >/dev/null
    set_samconfig_parameter_override "$DEPLOY_ENV" "AgentCoreRuntimeArtifactBucket" "$bucket_name"
    set_samconfig_parameter_override "$DEPLOY_ENV" "AgentCoreRuntimeArtifactPrefix" "$artifact_key"

    echo "AgentCore Runtime:      required"
    echo "AgentCore Runtime name: $runtime_name"
    echo "Runtime artifact:       s3://$bucket_name/$artifact_key"
    if [ "$FORCE_AGENTCORE_RUNTIME_UPDATE" = true ]; then
        echo "Runtime update:         forced via unique artifact key"
    fi
}

write_samconfig_env() {
    local env_name="$1"
    local stack_name="$2"
    local region="$3"
    local parameter_overrides="$4"

    if [ ! -f "samconfig.toml" ]; then
        printf 'version = 0.1\n' > samconfig.toml
    fi

    {
        printf '\n[%s.deploy.parameters]\n' "$env_name"
        printf 'stack_name = "%s"\n' "$(toml_escape "$stack_name")"
        printf 'resolve_s3 = true\n'
        printf 's3_prefix = "%s"\n' "$(toml_escape "$stack_name")"
        printf 'region = "%s"\n' "$(toml_escape "$region")"
        printf 'capabilities = "%s"\n' "$SAM_CAPABILITIES"
        printf 'confirm_changeset = true\n'
        printf 'parameter_overrides = "%s"\n' "$parameter_overrides"
    } >> samconfig.toml
}

add_parameter_override() {
    local key="$1"
    local value="$2"
    local escaped_value

    escaped_value=$(toml_escape "$value")
    if [ -n "$PARAMETER_OVERRIDES_CONFIG" ]; then
        PARAMETER_OVERRIDES_CONFIG+=" "
    fi
    PARAMETER_OVERRIDES_CONFIG+="$key=\\\"$escaped_value\\\""
}

configure_new_env() {
    local default_stack
    local stream_url
    local spotify_client_id
    local spotify_client_secret
    local enable_spotify_validation
    local enable_spotify_playlists
    local custom_domain_name
    local cloudfront_certificate_arn
    local campaign_model_id
    local campaign_model_endpoint
    local campaign_model_arn
    local agentcore_memory_name
    local agentcore_runtime_name

    default_stack=$(resource_name_default "$DEPLOY_ENV" "muddys-top-10")

    if [ "$STACK_NAME_OVERRIDDEN" = false ]; then
        STACK_NAME=$(prompt_with_default "Stack name" "$default_stack")
    fi

    DEPLOY_REGION=$(prompt_with_default "AWS Region" "$DEPLOY_REGION")
    stream_url=$(prompt_with_default "Stream URL" "http://muddys.digistream.info:20398/stats?sid=1")

    PARAMETER_OVERRIDES_CONFIG=""
    add_parameter_override "StreamUrl" "$stream_url"

    enable_spotify_validation="true"
    if ! prompt_yes_no "Enable Spotify as a track validation source for this environment?" "y"; then
        enable_spotify_validation="false"
    fi
    add_parameter_override "EnableSpotifyValidation" "$enable_spotify_validation"

    enable_spotify_playlists="false"
    if prompt_yes_no "Enable Spotify OAuth and playlist generation for this environment?" "n"; then
        enable_spotify_playlists="true"
    fi
    add_parameter_override "EnableSpotifyPlaylists" "$enable_spotify_playlists"
    add_parameter_override "EnableSpotify" "$enable_spotify_playlists"

    if { [ "$enable_spotify_validation" = "true" ] || [ "$enable_spotify_playlists" = "true" ]; } && prompt_yes_no "Configure Spotify credentials for this environment?" "n"; then
        spotify_client_id=$(prompt_with_default "Spotify client ID" "")
        spotify_client_secret=$(prompt_secret_optional "Spotify client secret")

        if [ -n "$spotify_client_id" ]; then
            add_parameter_override "SpotifyClientId" "$spotify_client_id"
        fi

        if [ -n "$spotify_client_secret" ]; then
            add_parameter_override "SpotifyClientSecret" "$spotify_client_secret"
        fi
    fi

    if prompt_yes_no "Configure a custom CloudFront hostname for this environment?" "n"; then
        custom_domain_name=$(prompt_with_default "CloudFront custom hostname" "")
        cloudfront_certificate_arn=$(prompt_with_default "ACM certificate ARN in us-east-1" "")

        if [ -n "$custom_domain_name" ]; then
            add_parameter_override "CustomDomainName" "$custom_domain_name"
        fi

        if [ -n "$cloudfront_certificate_arn" ]; then
            add_parameter_override "CloudFrontCertificateArn" "$cloudfront_certificate_arn"
        fi
    fi

    agentcore_memory_name=$(prompt_with_default "AgentCore Memory name" "$(agentcore_memory_name_default "$DEPLOY_ENV")")
    add_parameter_override "AgentCoreMemoryName" "$agentcore_memory_name"

    agentcore_runtime_name=$(prompt_with_default "AgentCore Runtime name" "$(agentcore_runtime_name_default "$DEPLOY_ENV")")
    add_parameter_override "AgentCoreRuntimeName" "$agentcore_runtime_name"

    if prompt_yes_no "Configure Bedrock model-backed campaign generation?" "n"; then
        campaign_model_id=$(prompt_with_default "Campaign Bedrock model ID" "deepseek.v3.2")
        campaign_model_endpoint=$(prompt_with_default "Campaign model endpoint" "bedrock-mantle")

        if [ -n "$campaign_model_id" ]; then
            add_parameter_override "CampaignModelId" "$campaign_model_id"
        fi

        if [ -n "$campaign_model_endpoint" ]; then
            add_parameter_override "CampaignModelEndpoint" "$campaign_model_endpoint"
        fi

        if [ "$campaign_model_endpoint" = "bedrock-runtime" ]; then
            campaign_model_arn=$(prompt_with_default "Campaign Bedrock runtime model resource ARN" "")
            add_parameter_override "CampaignModelResourceArn" "$campaign_model_arn"
        fi
        if [ "$campaign_model_endpoint" = "strands-openai-responses" ]; then
            campaign_model_api_key_secret_arn=$(prompt_with_default "Campaign model API key secret ARN" "")
            add_parameter_override "CampaignModelApiKeySecretArn" "$campaign_model_api_key_secret_arn"
        fi
    fi

    write_samconfig_env "$DEPLOY_ENV" "$STACK_NAME" "$DEPLOY_REGION" "$PARAMETER_OVERRIDES_CONFIG"
}

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help|-help)
            usage
            exit 0
            ;;
        --env)
            if [ -z "${2:-}" ]; then
                echo "Error: --env requires a value"
                exit 1
            fi
            DEPLOY_ENV="$2"
            shift 2
            ;;
        --stack-name)
            if [ -z "${2:-}" ]; then
                echo "Error: --stack-name requires a value"
                exit 1
            fi
            STACK_NAME="$2"
            STACK_NAME_OVERRIDDEN=true
            shift 2
            ;;
        --agentcore-memory-name)
            if [ -z "${2:-}" ]; then
                echo "Error: --agentcore-memory-name requires a value"
                exit 1
            fi
            AGENTCORE_MEMORY_NAME_OVERRIDE="$2"
            shift 2
            ;;
        --agentcore-runtime-name)
            if [ -z "${2:-}" ]; then
                echo "Error: --agentcore-runtime-name requires a value"
                exit 1
            fi
            AGENTCORE_RUNTIME_NAME_OVERRIDE="$2"
            shift 2
            ;;
        --campaign-model-id)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-model-id requires a value"
                exit 1
            fi
            CAMPAIGN_MODEL_ID_OVERRIDE="$2"
            shift 2
            ;;
        --campaign-model-endpoint)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-model-endpoint requires a value"
                exit 1
            fi
            case "$2" in
                bedrock-mantle|bedrock-runtime|strands-openai-responses) ;;
                *)
                    echo "Error: --campaign-model-endpoint must be bedrock-mantle, bedrock-runtime, or strands-openai-responses"
                    exit 1
                    ;;
            esac
            CAMPAIGN_MODEL_ENDPOINT_OVERRIDE="$2"
            shift 2
            ;;
        --campaign-model-arn)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-model-arn requires a value"
                exit 1
            fi
            CAMPAIGN_MODEL_RESOURCE_ARN_OVERRIDE="$2"
            shift 2
            ;;
        --campaign-model-api-key-secret-arn)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-model-api-key-secret-arn requires a value"
                exit 1
            fi
            CAMPAIGN_MODEL_API_KEY_SECRET_ARN_OVERRIDE="$2"
            shift 2
            ;;
        --clear-campaign-model)
            CAMPAIGN_MODEL_ID_OVERRIDE="__CLEAR__"
            CAMPAIGN_MODEL_ENDPOINT_OVERRIDE="__CLEAR__"
            CAMPAIGN_MODEL_RESOURCE_ARN_OVERRIDE="__CLEAR__"
            CAMPAIGN_MODEL_API_KEY_SECRET_ARN_OVERRIDE="__CLEAR__"
            shift
            ;;
        --campaign-image-model-id)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-image-model-id requires a value"
                exit 1
            fi
            CAMPAIGN_IMAGE_MODEL_ID_OVERRIDE="$2"
            shift 2
            ;;
        --campaign-image-model-api-key-secret-arn)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-image-model-api-key-secret-arn requires a value"
                exit 1
            fi
            CAMPAIGN_IMAGE_MODEL_API_KEY_SECRET_ARN_OVERRIDE="$2"
            shift 2
            ;;
        --campaign-image-size)
            if [ -z "${2:-}" ]; then
                echo "Error: --campaign-image-size requires a value"
                exit 1
            fi
            CAMPAIGN_IMAGE_SIZE_OVERRIDE="$2"
            shift 2
            ;;
        --clear-campaign-image-model)
            CAMPAIGN_IMAGE_MODEL_ID_OVERRIDE="__CLEAR__"
            CAMPAIGN_IMAGE_MODEL_API_KEY_SECRET_ARN_OVERRIDE="__CLEAR__"
            CAMPAIGN_IMAGE_SIZE_OVERRIDE="__CLEAR__"
            shift
            ;;
        --enable-spotify)
            ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE="true"
            shift
            ;;
        --disable-spotify)
            ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE="false"
            shift
            ;;
        --enable-spotify-validation)
            ENABLE_SPOTIFY_VALIDATION_OVERRIDE="true"
            shift
            ;;
        --disable-spotify-validation)
            ENABLE_SPOTIFY_VALIDATION_OVERRIDE="false"
            shift
            ;;
        --enable-spotify-playlists)
            ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE="true"
            shift
            ;;
        --disable-spotify-playlists)
            ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE="false"
            shift
            ;;
        --lambda-arch)
            if [ -z "${2:-}" ]; then
                echo "Error: --lambda-arch requires a value"
                exit 1
            fi
            case "$2" in
                x86_64|arm64) ;;
                *)
                    echo "Error: --lambda-arch must be x86_64 or arm64"
                    exit 1
                    ;;
            esac
            LAMBDA_ARCHITECTURE_OVERRIDE="$2"
            shift 2
            ;;
        --arm64)
            LAMBDA_ARCHITECTURE_OVERRIDE="arm64"
            shift
            ;;
        --x86-64)
            LAMBDA_ARCHITECTURE_OVERRIDE="x86_64"
            shift
            ;;
        --no-container-build)
            USE_CONTAINER_BUILD=false
            shift
            ;;
        --force-agentcore-runtime-update)
            FORCE_AGENTCORE_RUNTIME_UPDATE=true
            shift
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo ""
            usage
            exit 1
            ;;
    esac
done

if ! echo "$DEPLOY_ENV" | grep -Eq '^[A-Za-z0-9_-]+$'; then
    echo "Error: --env must contain only letters, numbers, underscores, or hyphens"
    exit 1
fi

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Muddy's Music Cafe - Top 10 Tracker                   ║"
echo "║                   Deployment Script                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Step 0: Check prerequisites
echo "🔎 Step 0: Checking prerequisites..."
echo "─────────────────────────────────────────────────────────────────"

for command in sam aws curl sed; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "❌ Error: Required command not found on PATH: $command"
        exit 1
    fi
done

if [ "$USE_CONTAINER_BUILD" = true ]; then
    if ! command -v docker >/dev/null 2>&1; then
        echo "❌ Error: Docker is required for the default containerized SAM build but was not found on PATH"
        echo "Install/start Docker, or rerun with --no-container-build if python3.14 is available locally."
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        echo "❌ Error: Docker is installed but the daemon is not reachable"
        echo "Start Docker, then rerun this script."
        exit 1
    fi
else
    if ! command -v python3.14 >/dev/null 2>&1; then
        echo "❌ Error: python3.14 is required when using --no-container-build"
        echo "Use the default containerized build or make python3.14 available on PATH."
        exit 1
    fi
fi

echo "✅ Prerequisites available"
echo ""

ENV_EXISTS=false
PARAMETER_OVERRIDES_CONFIG=""
if config_env_exists "$DEPLOY_ENV"; then
    ENV_EXISTS=true
    CONFIG_STACK_NAME=$(samconfig_value "$DEPLOY_ENV" "stack_name")
    if [ "$STACK_NAME_OVERRIDDEN" = false ] && [ -n "$CONFIG_STACK_NAME" ]; then
        STACK_NAME="$CONFIG_STACK_NAME"
    fi
else
    configure_new_env
fi

set_samconfig_parameter_override "$DEPLOY_ENV" "EnableAgentCoreGateway" ""
set_samconfig_parameter_override "$DEPLOY_ENV" "EnableAgentCoreMemory" ""

if [ -z "$(samconfig_parameter_override_value "$DEPLOY_ENV" "AgentCoreMemoryName")" ] && [ -z "$AGENTCORE_MEMORY_NAME_OVERRIDE" ]; then
    AGENTCORE_MEMORY_NAME_OVERRIDE="$(agentcore_memory_name_default "$DEPLOY_ENV")"
fi

if [ -n "$AGENTCORE_MEMORY_NAME_OVERRIDE" ]; then
    set_samconfig_parameter_override "$DEPLOY_ENV" "AgentCoreMemoryName" "$AGENTCORE_MEMORY_NAME_OVERRIDE"
    echo "AgentCore Memory name:  $AGENTCORE_MEMORY_NAME_OVERRIDE (saved to samconfig.toml)"
fi

echo "AgentCore Gateway:      required"
echo "AgentCore Memory:       required"

if [ -z "$(samconfig_parameter_override_value "$DEPLOY_ENV" "AgentCoreRuntimeName")" ] && [ -z "$AGENTCORE_RUNTIME_NAME_OVERRIDE" ]; then
    AGENTCORE_RUNTIME_NAME_OVERRIDE="$(agentcore_runtime_name_default "$DEPLOY_ENV")"
fi

if [ -n "$AGENTCORE_RUNTIME_NAME_OVERRIDE" ]; then
    set_samconfig_parameter_override "$DEPLOY_ENV" "AgentCoreRuntimeName" "$AGENTCORE_RUNTIME_NAME_OVERRIDE"
    echo "AgentCore Runtime name: $AGENTCORE_RUNTIME_NAME_OVERRIDE (saved to samconfig.toml)"
fi

if [ -n "$ENABLE_SPOTIFY_VALIDATION_OVERRIDE" ]; then
    set_samconfig_parameter_override "$DEPLOY_ENV" "EnableSpotifyValidation" "$ENABLE_SPOTIFY_VALIDATION_OVERRIDE"
fi

if [ -n "$ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE" ]; then
    set_samconfig_parameter_override "$DEPLOY_ENV" "EnableSpotifyPlaylists" "$ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE"
    set_samconfig_parameter_override "$DEPLOY_ENV" "EnableSpotify" "$ENABLE_SPOTIFY_PLAYLISTS_OVERRIDE"
fi

ENABLE_SPOTIFY_VALIDATION_EFFECTIVE="$(samconfig_parameter_override_value "$DEPLOY_ENV" "EnableSpotifyValidation")"
if [ -z "$ENABLE_SPOTIFY_VALIDATION_EFFECTIVE" ]; then
    ENABLE_SPOTIFY_VALIDATION_EFFECTIVE="true"
    set_samconfig_parameter_override "$DEPLOY_ENV" "EnableSpotifyValidation" "$ENABLE_SPOTIFY_VALIDATION_EFFECTIVE"
fi

ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE="$(samconfig_parameter_override_value "$DEPLOY_ENV" "EnableSpotifyPlaylists")"
if [ -z "$ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE" ]; then
    ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE="$(samconfig_parameter_override_value "$DEPLOY_ENV" "EnableSpotify")"
    if [ -z "$ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE" ]; then
        ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE="false"
    fi
    set_samconfig_parameter_override "$DEPLOY_ENV" "EnableSpotifyPlaylists" "$ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE"
fi
echo "Spotify validation:     $ENABLE_SPOTIFY_VALIDATION_EFFECTIVE"
echo "Spotify playlists:      $ENABLE_SPOTIFY_PLAYLISTS_EFFECTIVE"

if [ -n "$LAMBDA_ARCHITECTURE_OVERRIDE" ]; then
    set_samconfig_parameter_override "$DEPLOY_ENV" "LambdaArchitecture" "$LAMBDA_ARCHITECTURE_OVERRIDE"
fi

LAMBDA_ARCHITECTURE_EFFECTIVE="$(samconfig_parameter_override_value "$DEPLOY_ENV" "LambdaArchitecture")"
if [ -z "$LAMBDA_ARCHITECTURE_EFFECTIVE" ]; then
    LAMBDA_ARCHITECTURE_EFFECTIVE="x86_64"
fi
echo "Lambda architecture:    $LAMBDA_ARCHITECTURE_EFFECTIVE"

if [ -n "$CAMPAIGN_MODEL_ID_OVERRIDE" ]; then
    if [ "$CAMPAIGN_MODEL_ID_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelId" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelId" "$CAMPAIGN_MODEL_ID_OVERRIDE"
    fi
fi

if [ -n "$CAMPAIGN_MODEL_ENDPOINT_OVERRIDE" ]; then
    if [ "$CAMPAIGN_MODEL_ENDPOINT_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelEndpoint" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelEndpoint" "$CAMPAIGN_MODEL_ENDPOINT_OVERRIDE"
    fi
fi

if [ -n "$CAMPAIGN_MODEL_RESOURCE_ARN_OVERRIDE" ]; then
    if [ "$CAMPAIGN_MODEL_RESOURCE_ARN_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelResourceArn" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelResourceArn" "$CAMPAIGN_MODEL_RESOURCE_ARN_OVERRIDE"
    fi
fi

if [ -n "$CAMPAIGN_MODEL_API_KEY_SECRET_ARN_OVERRIDE" ]; then
    if [ "$CAMPAIGN_MODEL_API_KEY_SECRET_ARN_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelApiKeySecretArn" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignModelApiKeySecretArn" "$CAMPAIGN_MODEL_API_KEY_SECRET_ARN_OVERRIDE"
    fi
fi

if [ -n "$CAMPAIGN_IMAGE_MODEL_ID_OVERRIDE" ]; then
    if [ "$CAMPAIGN_IMAGE_MODEL_ID_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignImageModelId" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignImageModelId" "$CAMPAIGN_IMAGE_MODEL_ID_OVERRIDE"
    fi
fi

if [ -n "$CAMPAIGN_IMAGE_MODEL_API_KEY_SECRET_ARN_OVERRIDE" ]; then
    if [ "$CAMPAIGN_IMAGE_MODEL_API_KEY_SECRET_ARN_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignImageModelApiKeySecretArn" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignImageModelApiKeySecretArn" "$CAMPAIGN_IMAGE_MODEL_API_KEY_SECRET_ARN_OVERRIDE"
    fi
fi

if [ -n "$CAMPAIGN_IMAGE_SIZE_OVERRIDE" ]; then
    if [ "$CAMPAIGN_IMAGE_SIZE_OVERRIDE" = "__CLEAR__" ]; then
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignImageSize" ""
    else
        set_samconfig_parameter_override "$DEPLOY_ENV" "CampaignImageSize" "$CAMPAIGN_IMAGE_SIZE_OVERRIDE"
    fi
fi

echo "Deployment environment: $DEPLOY_ENV"
echo "Stack name:             $STACK_NAME"
if [ "$ENV_EXISTS" = true ]; then
    echo "SAM config:             found"
else
    echo "SAM config:             created"
fi
echo ""

# Step 0.5: Package AgentCore Runtime source
echo "🧠 Step 0.5: Packaging AgentCore Runtime..."
echo "─────────────────────────────────────────────────────────────────"
package_agentcore_runtime
echo "✅ AgentCore Runtime package uploaded"
echo ""

# Step 1: Build SAM application
echo "📦 Step 1: Building SAM application..."
echo "─────────────────────────────────────────────────────────────────"
if [ "$USE_CONTAINER_BUILD" = true ]; then
    echo "Using containerized SAM build for Lambda runtime python3.14"
    sam build --use-container
else
    echo "Using local SAM build with python3.14 from PATH"
    sam build
fi
echo "✅ Build complete"
echo ""

# Step 2: Deploy SAM stack
echo "🚀 Step 2: Deploying SAM stack..."
echo "─────────────────────────────────────────────────────────────────"
if [ "$ENV_EXISTS" = false ]; then
    echo "Using newly created SAM configuration for environment: $DEPLOY_ENV"
    sam deploy --config-env "$DEPLOY_ENV" --capabilities $SAM_CAPABILITIES --no-fail-on-empty-changeset
else
    echo "Using existing SAM configuration for environment: $DEPLOY_ENV"
    if [ "$STACK_NAME_OVERRIDDEN" = true ]; then
        sam deploy --config-env "$DEPLOY_ENV" --stack-name "$STACK_NAME" --capabilities $SAM_CAPABILITIES --no-fail-on-empty-changeset
    else
        sam deploy --config-env "$DEPLOY_ENV" --capabilities $SAM_CAPABILITIES --no-fail-on-empty-changeset
    fi
fi
echo "✅ Stack deployed"
echo ""

# Step 3: Get stack outputs
echo "📊 Step 3: Reading stack outputs..."
echo "─────────────────────────────────────────────────────────────────"

# Get API URL
API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

if [ -z "$API_URL" ] || [ "$API_URL" = "None" ]; then
    echo "❌ Error: Could not retrieve API URL from stack outputs"
    exit 1
fi

echo "API URL: $API_URL"

# Get S3 bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
    --output text)

if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" = "None" ]; then
    echo "❌ Error: Could not retrieve S3 bucket name from stack outputs"
    exit 1
fi

echo "S3 Bucket: $BUCKET_NAME"

# Get CloudFront Distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text)

if [ -z "$DISTRIBUTION_ID" ] || [ "$DISTRIBUTION_ID" = "None" ]; then
    echo "⚠️  Warning: Could not retrieve CloudFront distribution ID"
else
    echo "CloudFront Distribution: $DISTRIBUTION_ID"
fi

# Get CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
    --output text)

if [ -z "$CLOUDFRONT_URL" ] || [ "$CLOUDFRONT_URL" = "None" ]; then
    echo "❌ Error: Could not retrieve frontend CloudFront URL from stack outputs"
    exit 1
fi

# Get raw CloudFront domain name (CNAME target)
CLOUDFRONT_DOMAIN_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomainName`].OutputValue' \
    --output text)

RAW_CLOUDFRONT_URL=""
if [ -n "$CLOUDFRONT_DOMAIN_NAME" ] && [ "$CLOUDFRONT_DOMAIN_NAME" != "None" ]; then
    RAW_CLOUDFRONT_URL="https://$CLOUDFRONT_DOMAIN_NAME"
fi

# Get Cognito User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

# Get Cognito Client ID
CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

# Get Cognito Hosted UI URL
COGNITO_DOMAIN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoHostedUIUrl`].OutputValue' \
    --output text)

ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Parameters[?ParameterKey==`EnableSpotifyPlaylists`].ParameterValue' \
    --output text)

if [ -z "$ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED" ] || [ "$ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED" = "None" ]; then
    ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Parameters[?ParameterKey==`EnableSpotify`].ParameterValue' \
        --output text)
fi

if [ -z "$ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED" ] || [ "$ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED" = "None" ]; then
    ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED="false"
fi

if [ -n "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ]; then
    echo "Cognito User Pool: $USER_POOL_ID"
    echo "Cognito Client ID: $CLIENT_ID"
    echo "Cognito Domain: $COGNITO_DOMAIN"
fi
echo "Spotify playlists: $ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED"

echo "✅ Outputs retrieved"
echo ""

# Step 4: Configure frontend
echo "⚙️  Step 4: Configuring frontend with API endpoint..."
echo "─────────────────────────────────────────────────────────────────"

if [ ! -f "$FRONTEND_SOURCE" ]; then
    echo "❌ Error: Frontend source file not found: $FRONTEND_SOURCE"
    exit 1
fi

# Configure admin.html if Cognito is configured
if [ -f "$ADMIN_SOURCE" ] && [ -n "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ]; then
    echo "Configuring index.html with Cognito..."
    sed -e "s|%%API_ENDPOINT%%|$API_URL|g" \
        -e "s|%%USER_POOL_ID%%|$USER_POOL_ID|g" \
        -e "s|%%CLIENT_ID%%|$CLIENT_ID|g" \
        -e "s|%%COGNITO_DOMAIN%%|$COGNITO_DOMAIN|g" \
        -e "s|%%ENABLE_SPOTIFY%%|$ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED|g" \
        "$FRONTEND_SOURCE" > "$FRONTEND_BUILD"
    echo "✅ index.html configured"

    echo "Configuring admin.html with Cognito..."
    sed -e "s|%%API_ENDPOINT%%|$API_URL|g" \
        -e "s|%%USER_POOL_ID%%|$USER_POOL_ID|g" \
        -e "s|%%CLIENT_ID%%|$CLIENT_ID|g" \
        -e "s|%%COGNITO_DOMAIN%%|$COGNITO_DOMAIN|g" \
        -e "s|%%ENABLE_SPOTIFY%%|$ENABLE_SPOTIFY_PLAYLISTS_DEPLOYED|g" \
        "$ADMIN_SOURCE" > "$ADMIN_BUILD"
    echo "✅ admin.html configured"
else
    sed "s|%%API_ENDPOINT%%|$API_URL|g" "$FRONTEND_SOURCE" > "$FRONTEND_BUILD"
    echo "⚠️  Skipping admin.html (Cognito not configured or file not found)"
fi

# Configure data-viewer.html
if [ -f "$DATA_VIEWER_SOURCE" ]; then
    echo "Configuring data-viewer.html..."
    sed "s|%%API_ENDPOINT%%|$API_URL|g" "$DATA_VIEWER_SOURCE" > "$DATA_VIEWER_BUILD"
    echo "✅ data-viewer.html configured"
fi

echo ""

# Step 5: Upload frontend to S3
echo "📤 Step 5: Uploading frontend to S3..."
echo "─────────────────────────────────────────────────────────────────"

# Upload index.html
aws s3 cp "$FRONTEND_BUILD" "s3://$BUCKET_NAME/index.html" \
    --content-type "text/html" \
    --cache-control "max-age=300"
echo "✅ index.html uploaded"

# Upload admin.html if configured
if [ -f "$ADMIN_BUILD" ]; then
    aws s3 cp "$ADMIN_BUILD" "s3://$BUCKET_NAME/admin.html" \
        --content-type "text/html" \
        --cache-control "max-age=300"
    echo "✅ admin.html uploaded"
fi

# Upload data-viewer.html if configured
if [ -f "$DATA_VIEWER_BUILD" ]; then
    aws s3 cp "$DATA_VIEWER_BUILD" "s3://$BUCKET_NAME/data-viewer.html" \
        --content-type "text/html" \
        --cache-control "max-age=300"
    echo "✅ data-viewer.html uploaded"
fi

# Upload assets folder if it exists
if [ -d "frontend/assets" ]; then
    echo "📁 Uploading assets..."
    aws s3 sync frontend/assets "s3://$BUCKET_NAME/assets" \
        --cache-control "max-age=31536000"
    echo "✅ Assets uploaded"
fi

echo ""

# Step 6: Update Cognito callback URLs
if [ -n "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ] && [ -n "$CLIENT_ID" ] && [ "$CLIENT_ID" != "None" ] && [ -n "$CLOUDFRONT_URL" ]; then
    echo "🔐 Step 6: Updating Cognito callback URLs..."
    echo "─────────────────────────────────────────────────────────────────"

    CALLBACK_URLS=("${CLOUDFRONT_URL}/index.html" "${CLOUDFRONT_URL}/admin.html" "http://localhost:8000/index.html" "http://localhost:8000/admin.html")
    if [ -n "$RAW_CLOUDFRONT_URL" ] && [ "$RAW_CLOUDFRONT_URL" != "$CLOUDFRONT_URL" ]; then
        CALLBACK_URLS+=("${RAW_CLOUDFRONT_URL}/index.html" "${RAW_CLOUDFRONT_URL}/admin.html")
    fi

    # Update callback and logout URLs
    aws cognito-idp update-user-pool-client \
        --user-pool-id "$USER_POOL_ID" \
        --client-id "$CLIENT_ID" \
        --callback-urls "${CALLBACK_URLS[@]}" \
        --logout-urls "${CALLBACK_URLS[@]}" \
        --allowed-o-auth-flows "code" "implicit" \
        --allowed-o-auth-scopes "email" "openid" "profile" \
        --allowed-o-auth-flows-user-pool-client \
        --supported-identity-providers "COGNITO" > /dev/null

    echo "✅ Cognito callback URLs updated"
else
    echo "⚠️  Step 6: Skipping Cognito callback URL update"
fi
echo ""

# Step 7: Invalidate CloudFront cache
if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
    echo "🔄 Step 7: Invalidating CloudFront cache..."
    echo "─────────────────────────────────────────────────────────────────"

    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)

    echo "Invalidation ID: $INVALIDATION_ID"
    echo "✅ CloudFront cache invalidated"
    echo "⏳ Note: Invalidation may take a few minutes to complete"
else
    echo "⚠️  Step 7: Skipping CloudFront invalidation (no distribution ID)"
fi
echo ""

# Step 8: Test deployment
echo "🧪 Step 8: Testing deployment..."
echo "─────────────────────────────────────────────────────────────────"

echo "Skipping unauthenticated API health check because /api/health requires Cognito authentication."
echo "Testing CloudFront frontend endpoint..."
CLOUDFRONT_STATUS=$(curl -L -s -o /dev/null -w "%{http_code}" "$CLOUDFRONT_URL/")

if [ "$CLOUDFRONT_STATUS" = "200" ]; then
    echo "✅ CloudFront frontend is reachable"
else
    echo "⚠️  Warning: CloudFront returned status code: $CLOUDFRONT_STATUS"
    echo "   This can happen briefly after deployment or before custom domain DNS is pointed at CloudFront."
fi

echo ""

# Cleanup
rm -f "$FRONTEND_BUILD"
rm -f "$ADMIN_BUILD" "$DATA_VIEWER_BUILD"

# Final summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    DEPLOYMENT SUCCESSFUL!                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Deployment Summary:"
echo "─────────────────────────────────────────────────────────────────"
echo "Stack Name:       $STACK_NAME"
echo "API Endpoint:     $API_URL"
echo "S3 Bucket:        $BUCKET_NAME"
echo "Frontend URL:     $CLOUDFRONT_URL"
echo ""
echo "🎉 Your application is now live!"
echo ""
echo "🌐 Open your browser to: $CLOUDFRONT_URL"
if [ -n "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ]; then
    echo "🔐 Admin panel:       ${CLOUDFRONT_URL}/admin.html"
fi
echo ""

if [ -n "$USER_POOL_ID" ] && [ "$USER_POOL_ID" != "None" ]; then
    echo "🔐 First-time setup:"
    echo "  Create admin user: aws cognito-idp admin-create-user --user-pool-id $USER_POOL_ID --username admin@example.com --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true"
    echo ""
fi
echo "📊 View logs:"
echo "  Stream Poller: sam logs -n StreamPollerFunction --stack-name $STACK_NAME --tail"
echo "  API Handler:   sam logs -n ApiFunction --stack-name $STACK_NAME --tail"
echo ""
echo "🔧 Useful commands:"
echo "  View outputs:  aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs'"
echo "  Delete stack:  sam delete --stack-name $STACK_NAME"
echo "  Redeploy:      ./deploy.sh"
echo ""
echo "⏰ Note: Wait 5-10 minutes for tracks to start appearing in the app."
echo ""
echo "═══════════════════════════════════════════════════════════════════"
