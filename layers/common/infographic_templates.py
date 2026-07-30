"""Versioned infographic template resolution.

Templates are layout inputs for infographic generation. The generated campaign
asset remains an immutable HTML/CSS snapshot stored on the campaign record.
"""

import re


DEFAULT_TEMPLATE_ID = 'classic_chart_poster'
DEFAULT_TEMPLATE_VERSION = '1'

DEFAULT_TEMPLATE_CONFIG = {
    'template_id': DEFAULT_TEMPLATE_ID,
    'version': DEFAULT_TEMPLATE_VERSION,
    'source': 'built_in',
    'reference_png_key': '',
    'reference_png_generated_at': ''
}

TEMPLATE_OPTIONS = {
    DEFAULT_TEMPLATE_ID: {
        'template_id': DEFAULT_TEMPLATE_ID,
        'version': DEFAULT_TEMPLATE_VERSION,
        'name': 'Classic Chart Poster',
        'description': 'Dense branded chart table with chart facts, stats, and show information.',
        'source': 'built_in',
        'status': 'active'
    }
}

CLASSIC_CHART_POSTER_HTML = """
<section class="poster">
  <header class="masthead">
    <img class="logo" src="{{MUDDYS_LOGO_DATA_URI}}" alt="{{LOGO_ALT}}">
    <div class="title-block">
      <h1>{{CHART_TITLE}} <span>This Week</span></h1>
      <p>Music Cafe</p>
    </div>
    <aside class="date-block">
      <strong>{{SUBHEAD}}</strong>
      <small>Compiled from songs played by our DJs and patron requests</small>
    </aside>
  </header>
  <main class="main-grid">
    <section class="chart-panel">
      <div class="chart-heading"><span>#</span><span>Artist</span><span>Title</span><span>Plays</span><span>Vs Last Week</span></div>
      <ol class="chart">{{CHART_ROWS}}</ol>
    </section>
    <section class="talk"><h2>Chart Talk</h2>{{TALK_CARDS}}</section>
  </main>
  <section class="stats">
    <article><h3>This Week's Stats</h3><p><b>{{NEW_ENTRIES}}</b> new entries</p><p><b>{{CLIMBERS}}</b> climbers</p><p><b>{{FALLERS}}</b> fallers</p><p><b>{{NON_MOVERS}}</b> non-movers</p></article>
    <article><h3>Chart Facts</h3><p>#{{NUMBER_ONE_RANK}} belongs to {{NUMBER_ONE_ARTIST}}</p><p>{{LONGEST_RUNNER_ARTIST}} leads the long-run story</p><p>{{HISTORY_WEEKS}} history weeks available</p></article>
    <article><h3>Top 10 By The Numbers</h3><p><b>{{TOTAL_PLAYS}}</b> total plays</p><p><b>{{UNIQUE_TRACKS}}</b> unique tracks</p><p><b>{{DIFFERENT_ARTISTS}}</b> different artists</p></article>
  </section>
  <footer class="footer">
    <div><small>Catch the Top 10</small><strong>{{COUNTDOWN_DAY}}<br>{{COUNTDOWN_TIME}}</strong></div>
    <div><small>With</small><strong>DJ Toohey & JP</strong><em>The Australian Dynamic Duo!</em></div>
    <div class="venue">Join us live at <strong>Muddy's Music Cafe</strong><span>Where music & friends come together</span></div>
    <div class="badge">{{TAGLINE}}</div>
  </footer>
  <div class="strap">{{TAGLINE}} ★ Thank you for keeping Muddy's playing!</div>
</section>
""".strip()

CLASSIC_CHART_POSTER_CSS = """
.poster{width:1280px;height:720px;padding:14px 18px;background:radial-gradient(circle at 80% 0%,{{ACCENT_COLOR}}59,transparent 18%),radial-gradient(circle at 45% 80%,{{PRIMARY_COLOR}}6b,transparent 24%),linear-gradient(135deg,{{BACKGROUND_COLOR}},#10051f 48%,#020617);color:{{TEXT_COLOR}};font-family:{{FONT_FAMILY_CSS}};text-transform:uppercase;position:relative;overflow:hidden}.poster:before{content:"";position:absolute;inset:0;background:linear-gradient(transparent 95%,{{PRIMARY_COLOR}}33),repeating-linear-gradient(90deg,transparent 0 78px,{{PRIMARY_COLOR}}14 79px 80px);opacity:.5;pointer-events:none}.masthead{height:110px;display:grid;grid-template-columns:118px 1fr 340px;gap:18px;align-items:center;border-bottom:2px solid {{PRIMARY_COLOR}};position:relative;z-index:1}.logo{width:110px;height:110px;object-fit:contain;filter:drop-shadow(0 0 10px {{SECONDARY_COLOR}})}h1{margin:0;font-size:52px;line-height:.88;letter-spacing:.035em;text-shadow:0 3px 0 #000,0 0 18px {{PRIMARY_COLOR}}73}h1 span{color:{{PRIMARY_COLOR}}}.title-block p{margin:0 0 0 72px;color:{{SECONDARY_COLOR}};font-family:'Brush Script MT',cursive;font-size:34px;text-transform:none}.date-block{text-align:right;border-top:3px solid {{SECONDARY_COLOR}};border-bottom:3px solid {{SECONDARY_COLOR}};padding:8px 0}.date-block strong{display:block;font-size:23px}.date-block small{display:block;font-size:13px;line-height:1.25;color:#e5e7eb}.main-grid{display:grid;grid-template-columns:728px 1fr;gap:12px;margin-top:9px;position:relative;z-index:1}.chart-panel{height:350px;border:1px solid {{PRIMARY_COLOR}};background:linear-gradient(90deg,rgba(9,0,18,.95),rgba(9,0,18,.72));box-shadow:0 0 24px {{PRIMARY_COLOR}}2e}.chart-heading{height:25px;display:grid;grid-template-columns:56px 190px 1fr 70px 116px;align-items:center;color:{{SECONDARY_COLOR}};font-size:13px;letter-spacing:.08em;border-bottom:1px solid {{PRIMARY_COLOR}}a6;padding-right:8px}.chart-heading span{padding-left:10px}.chart{list-style:none;margin:0;padding:0}.chart li{height:32.4px;display:grid;grid-template-columns:56px 190px 1fr 70px 116px;align-items:center;border-bottom:1px solid {{PRIMARY_COLOR}}57}.chart li:last-child{border-bottom:0}.chart b{height:100%;display:grid;place-items:center;background:linear-gradient(135deg,{{PRIMARY_COLOR}},#4c1d95);font-size:30px;color:#fff}.chart span{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:900}.chart .artist{padding-left:12px;color:{{TEXT_COLOR}};font-size:21px}.chart .title{color:#e5e7eb;font-size:20px;text-transform:none}.chart em{color:{{PRIMARY_COLOR}};font-style:normal;font-size:15px;font-weight:900}.chart strong{font-size:14px;text-align:center;color:{{SECONDARY_COLOR}}}.chart .move-up strong{color:#22c55e}.chart .move-down strong{color:#ef4444}.chart .move-same strong{color:#d1d5db}.talk{height:350px;border:1px solid {{SECONDARY_COLOR}};background:rgba(0,0,0,.74);padding:35px 14px 12px;display:grid;grid-template-columns:1fr 1fr;gap:8px;position:relative;box-shadow:0 0 24px {{SECONDARY_COLOR}}21}.talk h2{position:absolute;top:-17px;left:50%;transform:translateX(-50%) skew(-8deg);margin:0;background:{{SECONDARY_COLOR}};color:#020617;padding:5px 42px;font-size:27px;font-style:italic;box-shadow:0 4px 0 rgba(0,0,0,.55)}.talk article{display:grid;grid-template-columns:42px 1fr;gap:9px;border-bottom:1px dotted rgba(255,255,255,.42);padding:7px}.talk article b{width:36px;height:36px;border:1px solid {{ACCENT_COLOR}};border-radius:999px;display:grid;place-items:center;color:{{SECONDARY_COLOR}};font-size:15px}.talk h3{margin:0 0 4px;color:{{SECONDARY_COLOR}};font-size:16px}.talk p{margin:0;color:#e5e7eb;font-size:12.5px;line-height:1.18;text-transform:none;font-weight:800}.stats{height:105px;margin-top:9px;border:1px solid {{PRIMARY_COLOR}};background:rgba(0,0,0,.75);display:grid;grid-template-columns:.82fr 1.16fr .98fr;position:relative;z-index:1}.stats article{padding:9px 13px;border-right:1px solid {{PRIMARY_COLOR}}8c}.stats article:last-child{border-right:0}.stats h3{margin:0 0 5px;color:{{SECONDARY_COLOR}};font-size:15px}.stats p{margin:0;color:#e5e7eb;font-size:12px;line-height:1.35}.stats b{color:{{SECONDARY_COLOR}};font-size:17px}.footer{height:92px;margin-top:8px;display:grid;grid-template-columns:240px 265px 1fr 112px;gap:16px;align-items:center;position:relative;z-index:1}.footer small{display:block;color:#d1d5db;font-size:15px}.footer strong{display:block;color:{{SECONDARY_COLOR}};font-size:22px}.footer em{display:block;color:{{SECONDARY_COLOR}};font-family:'Brush Script MT',cursive;font-size:18px;text-transform:none}.venue{text-align:center;color:#22c55e;font-size:23px;font-weight:900}.venue strong{display:block;color:{{TEXT_COLOR}};font-size:28px}.venue span{display:block;color:{{ACCENT_COLOR}};font-size:13px;letter-spacing:.08em}.badge{width:104px;height:104px;border:2px solid {{ACCENT_COLOR}};border-radius:999px;display:grid;place-items:center;text-align:center;color:{{TEXT_COLOR}};font-size:12px;line-height:1.15;box-shadow:0 0 18px {{ACCENT_COLOR}}d9;text-transform:none}.strap{position:absolute;left:0;right:0;bottom:6px;text-align:center;color:#cbd5e1;font-size:13px;letter-spacing:.08em;z-index:1}
""".strip()


def normalize_template_config(config):
    config = config if isinstance(config, dict) else {}
    source = str(config.get('source') or DEFAULT_TEMPLATE_CONFIG['source'])
    if source not in {'built_in', 's3'}:
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

    if source == 's3':
        normalized['s3_html_key'] = str(config.get('s3_html_key') or '').strip()
        normalized['s3_css_key'] = str(config.get('s3_css_key') or '').strip()
        if not normalized['s3_html_key'] or not normalized['s3_css_key']:
            return {
                **dict(DEFAULT_TEMPLATE_CONFIG),
                'reference_png_key': normalized['reference_png_key'],
                'reference_png_generated_at': normalized['reference_png_generated_at']
            }

    return normalized


def resolve_template(config=None, s3_client=None, bucket=None):
    normalized = normalize_template_config(config)
    if normalized['source'] == 's3':
        html = read_s3_text(s3_client, bucket, normalized['s3_html_key'])
        css = read_s3_text(s3_client, bucket, normalized['s3_css_key'])
        return {
            **normalized,
            'name': normalized['template_id'],
            'description': 'S3-backed infographic template',
            'html': html,
            'css': css
        }

    option = TEMPLATE_OPTIONS.get(normalized['template_id'], TEMPLATE_OPTIONS[DEFAULT_TEMPLATE_ID])
    return {
        **option,
        'html': CLASSIC_CHART_POSTER_HTML,
        'css': CLASSIC_CHART_POSTER_CSS
    }


def render_template(template, variables):
    html = replace_tokens(template['html'], variables)
    css = replace_tokens(template['css'], variables)
    return html, css


def template_public_options():
    return list(TEMPLATE_OPTIONS.values())


def replace_tokens(value, variables):
    rendered = value
    for key, replacement in variables.items():
        rendered = rendered.replace('{{' + key + '}}', str(replacement))
    unresolved = sorted(
        token
        for token in set(re.findall(r'{{\s*([A-Z0-9_]+)\s*}}', rendered))
        if token != 'MUDDYS_LOGO_DATA_URI'
    )
    if unresolved:
        raise ValueError(f"Infographic template has unresolved tokens: {', '.join(unresolved)}")
    return rendered


def sanitize_template_token(value, default):
    value = str(value or '').strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        return value
    return default


def read_s3_text(s3_client, bucket, key):
    if s3_client is None or not bucket:
        raise RuntimeError('S3 template source requested but S3 client or bucket is not configured')
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response['Body'].read().decode('utf-8')
