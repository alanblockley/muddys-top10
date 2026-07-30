"""Bedrock Prompt Management helpers for campaign generation."""
import json
import re


PROMPT_SECTIONS = ('radio_reads', 'infographic', 'social', 'infographic_asset')
PROMPT_REF_FIELDS = ('prompt_identifier', 'prompt_version', 'variant_name')
CODE_PROMPT_VERSION = 'agentic-campaign-v1'


def normalize_prompt_config(config):
    config = config if isinstance(config, dict) else {}
    normalized = {}
    for section in PROMPT_SECTIONS:
        raw = config.get(section)
        raw = raw if isinstance(raw, dict) else {}
        normalized[section] = {
            field: str(raw.get(field) or '').strip()
            for field in PROMPT_REF_FIELDS
        }
    return normalized


def prompt_ref_for_section(config, section_name):
    normalized = normalize_prompt_config(config)
    ref = normalized.get(section_name) or {}
    if not ref.get('prompt_identifier'):
        return None
    return ref


def code_prompt_ref(section_name):
    return {
        'source': 'code',
        'section': section_name,
        'prompt_version': CODE_PROMPT_VERSION
    }


def render_managed_prompt(section_name, prompt_config, variables, bedrock_agent_client=None):
    ref = prompt_ref_for_section(prompt_config, section_name)
    if not ref:
        return None

    if bedrock_agent_client is None:
        import boto3
        bedrock_agent_client = boto3.client('bedrock-agent')

    args = {
        'promptIdentifier': ref['prompt_identifier'],
        'includedData': 'ALL_DATA'
    }
    if ref.get('prompt_version'):
        args['promptVersion'] = ref['prompt_version']

    response = bedrock_agent_client.get_prompt(**args)
    template, variant_name = extract_prompt_template(response, ref.get('variant_name'))
    rendered = render_prompt_template(template, variables)
    return {
        'text': rendered,
        'ref': {
            'source': 'bedrock_prompt_management',
            'section': section_name,
            'prompt_identifier': ref['prompt_identifier'],
            'prompt_version': str(response.get('version') or ref.get('prompt_version') or ''),
            'prompt_arn': response.get('arn') or response.get('promptArn'),
            'variant_name': variant_name
        }
    }


def extract_prompt_template(response, variant_name=None):
    variants = response.get('variants') or []
    if not variants:
        raise ValueError('Bedrock prompt does not contain any variants')

    selected = None
    if variant_name:
        selected = next((variant for variant in variants if variant.get('name') == variant_name), None)
        if not selected:
            raise ValueError(f'Bedrock prompt variant not found: {variant_name}')
    if selected is None:
        default_variant = response.get('defaultVariant')
        selected = next((variant for variant in variants if variant.get('name') == default_variant), None)
    if selected is None:
        selected = variants[0]

    template_configuration = selected.get('templateConfiguration') or {}
    text = extract_text_template(template_configuration)
    if not text.strip():
        raise ValueError('Bedrock prompt template is empty')
    return text, selected.get('name')


def extract_text_template(template_configuration):
    text_config = template_configuration.get('text')
    if isinstance(text_config, dict):
        return str(text_config.get('text') or '')

    chat_config = template_configuration.get('chat')
    if isinstance(chat_config, dict):
        parts = []
        for system_part in chat_config.get('system') or []:
            text = system_part.get('text') if isinstance(system_part, dict) else None
            if text:
                parts.append(f'SYSTEM:\n{text}')
        for message in chat_config.get('messages') or []:
            if not isinstance(message, dict):
                continue
            role = str(message.get('role') or 'user').upper()
            content_parts = []
            for content in message.get('content') or []:
                text = content.get('text') if isinstance(content, dict) else None
                if text:
                    content_parts.append(text)
            if content_parts:
                parts.append(f'{role}:\n' + '\n'.join(content_parts))
        return '\n\n'.join(parts)

    return ''


def render_prompt_template(template, variables):
    values = {
        key: stringify_prompt_value(value)
        for key, value in variables.items()
    }

    def replace(match):
        key = match.group(1).strip()
        if key not in values:
            raise ValueError(f'Prompt template references unknown variable: {key}')
        return values[key]

    return re.sub(r'\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}', replace, template)


def stringify_prompt_value(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str, indent=2)
