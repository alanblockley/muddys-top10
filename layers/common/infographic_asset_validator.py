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
    re.compile(r'\son[a-z]+\s*=', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'https?://', re.IGNORECASE),
]

BLOCKED_CSS_PATTERNS = [
    re.compile(r'@import', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'https?://', re.IGNORECASE),
    re.compile(r'expression\s*\(', re.IGNORECASE),
]


def validate_infographic_asset(asset, chart_brief=None):
    """Validate an infographic asset for safety and structural correctness.

    Security checks (hard fail): blocks scripts, external URLs, event handlers.
    Structural checks (hard fail): canvas dimensions, non-empty HTML/CSS, size limits.
    Content checks (warnings only): presence of chart data in HTML.
    """
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

    # Security: block dangerous patterns
    errors.extend(pattern_errors('html', html, BLOCKED_HTML_PATTERNS))
    errors.extend(pattern_errors('css', css, BLOCKED_CSS_PATTERNS))

    # Content warnings (informational, do not block rendering)
    if chart_brief:
        tracks = (chart_brief.get('tracks') or [])[:10]
        found_tracks = sum(
            1 for track in tracks
            if (track.get('artist') or '') in html or (track.get('title') or '') in html
        )
        if found_tracks < 5:
            warnings.append(f'only {found_tracks}/10 tracks found in html — chart data may be incomplete')

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
