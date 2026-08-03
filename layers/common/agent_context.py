"""Load markdown agent specs and optional personal context files."""
import hashlib
import os
from pathlib import Path


AGENT_SPEC_FILES = {
    'infographic': '01a-Infographic-Agent-v3.md',
    'infographic_asset': '01b-Generate-Infographic-Asset.md',
    'social': '02-Social-Agent-v3.md',
    'radio': '03-Radio-Agent-v3.md'
}

CONTEXT_FILES = [
    # Domain knowledge (universal chart/radio conventions)
    'radio-chart-show-convention.md',
    'chart-show-glossary.md',
    'infographic-editorial-framework.md',
    'social-media-music-communities.md',
    # Personalisation (this show's voice and style)
    'personal-voice.md',
    'muddys-venue-context.md',
    'radio-read-examples.md',
    'social-style-examples.md',
    'words-and-phrases.md',
    'never-say.md'
]


def _candidate_roots(env_name, relative_path):
    roots = []
    if os.environ.get(env_name):
        roots.append(Path(os.environ[env_name]))

    cwd = Path.cwd()
    roots.extend([
        cwd / relative_path,
        cwd.parent / relative_path,
        Path('/opt') / relative_path.name,
        Path('/opt') / relative_path,
        Path('/opt') / 'agentic' / relative_path.name
    ])
    return roots


def _read_markdown_file(path):
    text = path.read_text(encoding='utf-8')
    return {
        'path': str(path),
        'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'content': text
    }


def load_agent_specs():
    specs = {}
    roots = _candidate_roots('AGENT_SPEC_ROOT', Path('docs/agent-spec'))

    for agent_name, filename in AGENT_SPEC_FILES.items():
        for root in roots:
            path = root / filename
            if path.exists():
                specs[agent_name] = _read_markdown_file(path)
                break

    return specs


def load_personal_context():
    context = []
    roots = _candidate_roots('AGENT_CONTEXT_ROOT', Path('docs/agentic/context'))

    for filename in CONTEXT_FILES:
        for root in roots:
            path = root / filename
            if path.exists():
                loaded = _read_markdown_file(path)
                if loaded['content'].strip():
                    context.append(loaded)
                break

    return context


def context_refs(agent_specs, personal_context):
    refs = []
    for agent_name, loaded in sorted(agent_specs.items()):
        refs.append({
            'kind': 'agent_spec',
            'name': agent_name,
            'path': loaded['path'],
            'sha256': loaded['sha256']
        })

    for loaded in personal_context:
        refs.append({
            'kind': 'personal_context',
            'path': loaded['path'],
            'sha256': loaded['sha256']
        })

    return refs
