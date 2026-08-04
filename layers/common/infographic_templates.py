"""Infographic template configuration management.

Templates are now rendered by chart-poster.js in the infographic-renderer Lambda.
This module handles template config storage and normalization only.
"""

import re


DEFAULT_TEMPLATE_ID = 'uploaded'
DEFAULT_TEMPLATE_VERSION = '1'

DEFAULT_TEMPLATE_CONFIG = {
    'template_id': DEFAULT_TEMPLATE_ID,
    'version': DEFAULT_TEMPLATE_VERSION,
    'source': 'uploaded',
    'reference_png_key': '',
    'reference_png_generated_at': ''
}


def normalize_template_config(config):
    config = config if isinstance(config, dict) else {}
    source = str(config.get('source') or DEFAULT_TEMPLATE_CONFIG['source'])
    if source not in {'built_in', 's3', 'uploaded'}:
        source = DEFAULT_TEMPLATE_CONFIG['source']

    template_id = sanitize_template_token(
        config.get('template_id') or DEFAULT_TEMPLATE_CONFIG['template_id'],
        DEFAULT_TEMPLATE_CONFIG['template_id']
    )
    version = sanitize_template_token(
        config.get('version') or DEFAULT_TEMPLATE_CONFIG['version'],
        DEFAULT_TEMPLATE_CONFIG['version']
    )

    normalized = {
        'template_id': template_id,
        'version': version,
        'source': source,
        'reference_png_key': str(config.get('reference_png_key') or '').strip(),
        'reference_png_generated_at': str(config.get('reference_png_generated_at') or '').strip()
    }

    if source == 'uploaded':
        normalized['s3_key'] = str(config.get('s3_key') or '').strip()
        normalized['name'] = str(config.get('name') or '').strip()
        normalized['content_type'] = str(config.get('content_type') or '').strip()
        if not normalized['s3_key']:
            return dict(DEFAULT_TEMPLATE_CONFIG)
        if normalized['s3_key'].lower().endswith('.png') and not normalized['reference_png_key']:
            normalized['reference_png_key'] = normalized['s3_key']
        return normalized

    if source == 's3':
        normalized['s3_html_key'] = str(config.get('s3_html_key') or '').strip()
        normalized['s3_css_key'] = str(config.get('s3_css_key') or '').strip()

    return normalized


def template_public_options():
    return []


def resolve_template(config=None, s3_client=None, bucket=None):
    """Resolve template configuration. Returns normalized config with metadata."""
    return normalize_template_config(config)


def sanitize_template_token(value, default):
    value = str(value or '').strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        return value
    return default
