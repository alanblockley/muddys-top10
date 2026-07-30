"""Validation for generated infographic HTML/CSS assets."""

import re


CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
MAX_HTML_LENGTH = 120000
MAX_CSS_LENGTH = 120000

BLOCKED_HTML_PATTERNS = [
    re.compile(r'<script\b', re.IGNORECASE),
    re.compile(r'<iframe\b', re.IGNORECASE),
    re.compile(r'<object\b', re.IGNORECASE),
    re.compile(r'<embed\b', re.IGNORECASE),
    re.compile(r'<link\b', re.IGNORECASE),
    re.compile(r'<meta\b', re.IGNORECASE),
    re.compile(r'\son[a-z]+\s*=', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'https?://', re.IGNORECASE),
    re.compile(r'src\s*=\s*["\']//', re.IGNORECASE),
]

BLOCKED_CSS_PATTERNS = [
    re.compile(r'@import', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'https?://', re.IGNORECASE),
    re.compile(r'url\(\s*["\']?//', re.IGNORECASE),
    re.compile(r'url\(\s*["\']?file:', re.IGNORECASE),
    re.compile(r'expression\s*\(', re.IGNORECASE),
]


def validate_infographic_asset(asset, chart_brief=None):
    errors = []
    warnings = []

    if not isinstance(asset, dict):
        return validation_result(False, ['infographic_asset must be an object'], warnings)

    canvas = asset.get('canvas')
    if not isinstance(canvas, dict):
        errors.append('canvas must be an object')
    else:
        if canvas.get('width') != CANVAS_WIDTH or canvas.get('height') != CANVAS_HEIGHT:
            errors.append('canvas must be exactly 1280x720')

    html = asset.get('html')
    css = asset.get('css')
    if not isinstance(html, str) or not html.strip():
        errors.append('html must be a non-empty string')
        html = ''
    if not isinstance(css, str) or not css.strip():
        errors.append('css must be a non-empty string')
        css = ''

    if len(html) > MAX_HTML_LENGTH:
        errors.append(f'html must be {MAX_HTML_LENGTH} characters or fewer')
    if len(css) > MAX_CSS_LENGTH:
        errors.append(f'css must be {MAX_CSS_LENGTH} characters or fewer')

    errors.extend(pattern_errors('html', html, BLOCKED_HTML_PATTERNS))
    errors.extend(pattern_errors('css', css, BLOCKED_CSS_PATTERNS))

    metadata = asset.get('metadata') if isinstance(asset.get('metadata'), dict) else {}
    branding = metadata.get('brand_config_snapshot') if isinstance(metadata.get('brand_config_snapshot'), dict) else {}
    chart_title = branding.get('chart_title') or branding.get('chart_title_text')
    tagline = branding.get('tagline') or branding.get('tagline_text')

    if '{{MUDDYS_LOGO_DATA_URI}}' not in html and '{{MUDDYS_LOGO_DATA_URI}}' not in css:
        errors.append('logo placeholder {{MUDDYS_LOGO_DATA_URI}} must be present')
    if chart_title and chart_title not in html and html_escape(chart_title) not in html:
        errors.append('exact chart title must be present in html')
    if tagline and tagline not in html and html_escape(tagline) not in html:
        errors.append('exact tag line must be present in html')

    if chart_brief:
        tracks = (chart_brief.get('tracks') or [])[:10]
        if len(tracks) < 10:
            warnings.append('chart brief has fewer than 10 tracks')
        for track in tracks:
            rank = str(track.get('rank') or '')
            artist = str(track.get('artist') or '').strip()
            title = str(track.get('title') or '').strip()
            if rank and f'>{rank}<' not in html and f'#{rank}' not in html:
                warnings.append(f'rank {rank} is not clearly visible in html')
            if artist and artist not in html:
                warnings.append(f'artist not found in html: {artist}')
            if title and title not in html:
                warnings.append(f'title not found in html: {title}')

    return validation_result(not errors, errors, warnings)


def validation_result(valid, errors, warnings):
    return {
        'valid': valid,
        'errors': errors,
        'warnings': warnings
    }


def pattern_errors(label, value, patterns):
    errors = []
    for pattern in patterns:
        if pattern.search(value):
            errors.append(f'{label} contains blocked content: {pattern.pattern}')
    return errors


def html_escape(value):
    return (
        str(value)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;')
    )
