"""Agentic campaign draft generation."""
import json
import os
import re
from copy import deepcopy
from decimal import Decimal
from datetime import datetime, timezone

from agent_context import context_refs, load_agent_specs, load_personal_context
from agent_memory import remember_campaign, retrieve_campaign_memory
from infographic_asset_validator import validate_infographic_asset
from infographic_templates import render_template, resolve_template
from prompt_management import code_prompt_ref, normalize_prompt_config, render_managed_prompt


DEFAULT_VENUE_CONFIG = {
    'venue': {
        'name': "Muddy's Music Cafe",
        'world': 'Second Life',
        'timezone': 'SLT',
        'countdown_day': 'Saturday',
        'countdown_time': '2:00am SLT',
        'slurl': 'https://maps.secondlife.com/secondlife/Muddys%20Music%20Cafe/103/123/22',
        'hosts': {
            'primary': 'DJ Toohey',
            'cohost': 'JP'
        },
        'chart_basis': 'Songs played at the venue during the previous 7 days plus listener requests.',
        'audience': {
            'style': 'Friendly, community-driven internet radio',
            'content_rating': 'PG'
        },
        'branding': {
            'tagline': 'Your requests. Your music. Your chart.'
        }
    }
}

BRANDING_OPTIONS = {
    'logo_variants': {
        'muddys_dog': {
            'label': "Muddy's dog logo",
            'alt': "Muddy's Music Cafe logo"
        }
    },
    'chart_titles': {
        'muddys_top10': "Muddy's Top 10",
        'muddys_music_cafe_top10': "Muddy's Music Cafe Top 10",
        'muddys_weekly_chart': "Muddy's Weekly Chart"
    },
    'taglines': {
        'your_requests': 'Your requests. Your music. Your chart.',
        'music_friends': 'Where music and friends come together.',
        'community_countdown': 'The countdown powered by our community.'
    },
    'color_schemes': {
        'neon_gold': {
            'label': 'Neon purple and gold',
            'primary_color': '#a855f7',
            'secondary_color': '#facc15',
            'accent_color': '#d946ef',
            'background_color': '#050005',
            'text_color': '#f8fafc'
        },
        'radio_gold': {
            'label': 'Classic radio gold',
            'primary_color': '#f59e0b',
            'secondary_color': '#111827',
            'accent_color': '#ef4444',
            'background_color': '#050505',
            'text_color': '#fff7ed'
        },
        'midnight_blue': {
            'label': 'Midnight blue',
            'primary_color': '#38bdf8',
            'secondary_color': '#facc15',
            'accent_color': '#fb7185',
            'background_color': '#020617',
            'text_color': '#e0f2fe'
        },
        'custom': {
            'label': 'Custom',
            'primary_color': '#a855f7',
            'secondary_color': '#facc15',
            'accent_color': '#d946ef',
            'background_color': '#050005',
            'text_color': '#f8fafc'
        }
    },
    'font_families': {
        'arial': {'label': 'Arial', 'font_family': "Arial, Helvetica, sans-serif"},
        'arial_black': {'label': 'Arial Black', 'font_family': "'Arial Black', Gadget, sans-serif"},
        'arial_narrow': {'label': 'Arial Narrow', 'font_family': "'Arial Narrow', Arial, sans-serif"},
        'verdana': {'label': 'Verdana', 'font_family': "Verdana, Geneva, sans-serif"},
        'tahoma': {'label': 'Tahoma', 'font_family': "Tahoma, Geneva, sans-serif"},
        'trebuchet': {'label': 'Trebuchet MS', 'font_family': "'Trebuchet MS', Helvetica, sans-serif"},
        'impact': {'label': 'Impact', 'font_family': "Impact, Charcoal, sans-serif"},
        'georgia': {'label': 'Georgia', 'font_family': "Georgia, serif"},
        'times': {'label': 'Times New Roman', 'font_family': "'Times New Roman', Times, serif"},
        'palatino': {'label': 'Palatino', 'font_family': "'Palatino Linotype', 'Book Antiqua', Palatino, serif"},
        'garamond': {'label': 'Garamond', 'font_family': "Garamond, Georgia, serif"},
        'courier': {'label': 'Courier New', 'font_family': "'Courier New', Courier, monospace"},
        'lucida_console': {'label': 'Lucida Console', 'font_family': "'Lucida Console', Monaco, monospace"},
        'brush_script': {'label': 'Brush Script MT', 'font_family': "'Brush Script MT', cursive"},
        'condensed_poster': {'label': 'Condensed poster', 'font_family': "'Arial Narrow','Trebuchet MS',sans-serif"},
        'clean_broadcast': {'label': 'Clean broadcast', 'font_family': "'Trebuchet MS','Verdana',sans-serif"},
        'classic_impact': {'label': 'Classic impact', 'font_family': "'Impact','Arial Black',sans-serif"}
    }
}

DEFAULT_CAMPAIGN_BRANDING = {
    'logo_variant': 'uploaded',
    'logo_s3_key': '',
    'logo_content_type': '',
    'logo_filename': '',
    'chart_title': "Muddy's Top 10",
    'tagline': 'Your requests. Your music. Your chart.',
    'color_scheme': 'neon_gold',
    'primary_color': '',
    'secondary_color': '',
    'accent_color': '',
    'background_color': '',
    'text_color': '',
    'font_family': 'condensed_poster'
}


def normalize_campaign_branding(config):
    config = config if isinstance(config, dict) else {}
    normalized = {}
    for key, default in DEFAULT_CAMPAIGN_BRANDING.items():
        if key in {'logo_s3_key', 'logo_content_type', 'logo_filename'}:
            normalized[key] = str(config.get(key) or default).strip()
            continue
        if key in {'chart_title', 'tagline'}:
            value = str(config.get(key) or default).strip()
            if key == 'chart_title':
                value = BRANDING_OPTIONS['chart_titles'].get(value, value)
            if key == 'tagline':
                value = BRANDING_OPTIONS['taglines'].get(value, value)
            normalized[key] = clamp_branding_text(value, default)
            continue
        if key in {'primary_color', 'secondary_color', 'accent_color', 'background_color', 'text_color'}:
            continue
        value = str(config.get(key, default))
        option_group = f'{key}s' if key != 'font_family' else 'font_families'
        if key == 'logo_variant':
            option_group = 'logo_variants'
        if key == 'color_scheme':
            option_group = 'color_schemes'
        if value not in BRANDING_OPTIONS[option_group]:
            value = default
        normalized[key] = value

    logo = BRANDING_OPTIONS['logo_variants'].get(normalized['logo_variant']) or BRANDING_OPTIONS['logo_variants']['muddys_dog']
    base_colors = BRANDING_OPTIONS['color_schemes'][normalized['color_scheme']]
    colors = {
        key: normalize_hex_color(config.get(key), base_colors[key])
        for key in ('primary_color', 'secondary_color', 'accent_color', 'background_color', 'text_color')
    }
    font = BRANDING_OPTIONS['font_families'][normalized['font_family']]
    normalized.update({
        'logo_alt': logo['alt'],
        'chart_title_text': normalized['chart_title'],
        'tagline_text': normalized['tagline'],
        **colors,
        'font_family_css': font['font_family']
    })
    return normalized


def clamp_branding_text(value, default):
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    if not text:
        return default
    return text[:96]


def normalize_hex_color(value, default):
    text = str(value or '').strip()
    if re.fullmatch(r'#[0-9A-Fa-f]{6}', text):
        return text.lower()
    if re.fullmatch(r'[0-9A-Fa-f]{6}', text):
        return f'#{text.lower()}'
    return default


def venue_config_with_branding(branding_config=None):
    venue_config = deepcopy(DEFAULT_VENUE_CONFIG)
    branding = normalize_campaign_branding(branding_config)
    venue_config['venue']['branding'] = {
        **venue_config['venue'].get('branding', {}),
        **branding,
        'tagline': branding['tagline_text'],
        'chart_title': branding['chart_title_text']
    }
    return venue_config

RADIO_READS_SCHEMA = {
    'intro': 'string',
    'top10_intro': 'string',
    'top5_recap': 'string',
    'top3_recap': 'string',
    'outro': 'string',
    'position_reads': [
        {
            'rank': 'number',
            'track': 'Artist - Title',
            'intro_line': 'string',
            'movement_line': 'string',
            'readout': 'string',
            'outro_hook': 'string'
        }
    ],
    'self_review': {
        'facts_verified': True,
        'pg_broadcast_appropriate': True,
        'missing_inputs': []
    }
}

INFOGRAPHIC_SCHEMA = {
    'headline': 'string',
    'subhead': 'string',
    'chart_story': 'string',
    'movement_summary': 'string',
    'statistics': [{'label': 'string', 'value': 'number or string'}],
    'track_cards': [
        {
            'rank': 'number',
            'display_text': 'Artist - Title',
            'movement_badge': 'string',
            'supporting_line': 'string'
        }
    ],
    'promotional_footer': 'string',
    'self_review': {
        'facts_verified': True,
        'ready_for_publication': True,
        'missing_inputs': []
    }
}

INFOGRAPHIC_ASSET_VERSION = 'agent-authored-html-css-v1'

INFOGRAPHIC_ASSET_SCHEMA = {
    'canvas': {
        'width': 1280,
        'height': 720
    },
    'metadata': {
        'design_summary': 'string',
        'visual_rationale': 'string'
    },
    'html': 'string',
    'css': 'string',
    'self_review': {
        'facts_verified': True,
        'brand_constraints_preserved': True,
        'template_used': True,
        'ready_for_render': True,
        'missing_inputs': []
    }
}

SOCIAL_SCHEMA = {
    'facebook': {
        'post': 'string',
        'hashtags': []
    },
    'primfeed': {
        'post': 'string',
        'hashtags': []
    },
    'discord': {
        'post': 'string'
    },
    'teaser': {
        'short_copy': 'string'
    },
    'alt_text': 'string',
    'self_review': {
        'facts_verified': True,
        'pg_appropriate': True,
        'missing_inputs': []
    }
}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def movement_text(track):
    movement = track.get('movement')
    delta = track.get('movement_delta')
    previous_rank = track.get('previous_rank')

    if movement == 'up' and delta:
        return f"up {delta} from #{previous_rank}"
    if movement == 'down' and delta is not None:
        return f"down {abs(delta)} from #{previous_rank}"
    if movement == 'same' and previous_rank:
        return f"holding steady at #{track['rank']}"
    if track.get('last_seen_week'):
        return f"returning to the chart after last appearing {track['last_seen_week']}"
    return 'new this week'


def clean_track_display(value):
    return re.sub(r'^\s*#?\d{1,2}\s*[.)\-:]\s*', '', str(value or '')).strip()


def track_label(track):
    artist = clean_track_display(track.get('artist'))
    title = clean_track_display(track.get('title'))
    if artist and title:
        return f"{artist} - {title}"
    return clean_track_display(track.get('track'))


def chart_story(chart_brief):
    tracks = chart_brief.get('tracks', [])
    notables = chart_brief.get('notables', {})
    number_one = notables.get('number_one') or (tracks[0] if tracks else None)
    climbers = notables.get('biggest_climbers') or []
    new_entries = notables.get('new_entries') or []

    if not number_one:
        return 'No chart entries are available for this week yet.'

    parts = [f"{track_label(number_one)} leads the Muddy's Top 10 at number one"]
    if climbers:
        top_climber = climbers[0]
        parts.append(f"while {track_label(top_climber)} makes the biggest move, {movement_text(top_climber)}")
    if new_entries:
        parts.append(f"and {len(new_entries)} track{'s' if len(new_entries) != 1 else ''} arrive new")
    return ', '.join(parts) + '.'


def validate_chart_brief(chart_brief):
    missing = []
    if not chart_brief.get('week_id'):
        missing.append('week_id')
    if not chart_brief.get('source_snapshot_key'):
        missing.append('source_snapshot_key')
    if not chart_brief.get('tracks'):
        missing.append('tracks')
    return missing


def generate_radio_reads(chart_brief, venue_config=None):
    venue = (venue_config or DEFAULT_VENUE_CONFIG)['venue']
    tracks = chart_brief.get('tracks', [])
    host = venue.get('hosts', {}).get('primary', 'your host')
    week_id = chart_brief.get('week_id')

    position_reads = []
    for track in tracks:
        play_count = track.get('play_count', 0)
        previous_rank = track.get('previous_rank')
        movement = movement_text(track)
        previous_context = (
            f"Last week it was #{previous_rank}; this week it is {movement}."
            if previous_rank
            else "There is no previous chart position to compare against this week."
        )
        position_reads.append({
            'rank': track['rank'],
            'track': track_label(track),
            'play_count': play_count,
            'previous_rank': previous_rank,
            'movement': track.get('movement'),
            'movement_delta': track.get('movement_delta'),
            'intro_line': f"At number {track['rank']}, it's {track_label(track)}.",
            'movement_line': movement.capitalize() + '.',
            'playout_line': f"{play_count} play{'s' if play_count != 1 else ''} counted in this chart window.",
            'readout': (
                f"{track_label(track)} lands at number {track['rank']} this week "
                f"with {play_count} play{'s' if play_count != 1 else ''} counted in the chart window. "
                f"{previous_context} That gives you a clean on-air cue before the next song."
            ),
            'outro_hook': f"Keep an ear on {track.get('artist') or track_label(track)} as the chart rolls into next week."
        })

    return {
        'intro': f"{host} here with the Muddy's Top 10 for week {week_id}.",
        'top10_intro': f"Built from the songs played around {venue['name']} and your requests, here is this week's countdown, from ten through to one.",
        'top5_recap': _recap(tracks[:5], 'Top 5'),
        'top3_recap': _recap(tracks[:3], 'Top 3'),
        'outro': f"That is this week's Muddy's Top 10. {venue.get('branding', {}).get('tagline', 'Your requests. Your music. Your chart.')}",
        'position_reads': position_reads,
        'self_review': {
            'facts_verified': True,
            'pg_broadcast_appropriate': True,
            'missing_inputs': validate_chart_brief(chart_brief)
        }
    }


def generate_radio_reads_with_model(chart_brief, venue_config, agent_spec, personal_context, memory_context, model_client, prompt_config=None, prompt_refs=None):
    fallback = generate_radio_reads(chart_brief, venue_config)
    return generate_section_with_model(
        'radio_reads',
        chart_brief,
        venue_config,
        agent_spec,
        personal_context,
        memory_context,
        model_client,
        fallback,
        RADIO_READS_SCHEMA,
        prompt_config=prompt_config,
        prompt_refs=prompt_refs
    )


def generate_infographic_content(chart_brief, venue_config=None):
    venue = (venue_config or venue_config_with_branding())['venue']
    branding = venue.get('branding', {})
    tracks = chart_brief.get('tracks', [])
    week_id = chart_brief.get('week_id')

    return {
        'headline': branding.get('chart_title', "Muddy's Top 10"),
        'subhead': f"Week of {week_id}",
        'chart_story': chart_story(chart_brief),
        'movement_summary': _movement_summary(chart_brief),
        'statistics': _statistics(chart_brief),
        'track_cards': [
            {
                'rank': track['rank'],
                'display_text': track_label(track),
                'movement_badge': movement_text(track).title(),
                'supporting_line': f"{track['play_count']} play{'s' if track['play_count'] != 1 else ''}"
            }
            for track in tracks
        ],
        'promotional_footer': branding.get('tagline', 'Your requests. Your music. Your chart.'),
        'self_review': {
            'facts_verified': True,
            'ready_for_publication': True,
            'missing_inputs': validate_chart_brief(chart_brief)
        }
    }


def generate_infographic_asset(chart_brief, infographic=None, venue_config=None, infographic_template=None):
    """Create an immutable authored HTML/CSS package for the campaign record.

    This is stored with the campaign so viewing a historical campaign does not
    reflow through whatever preview/template code exists in the admin UI later.
    """
    venue = (venue_config or venue_config_with_branding())['venue']
    branding = venue.get('branding', {})
    tracks = chart_brief.get('tracks', [])[:10]
    infographic = infographic or generate_infographic_content(chart_brief, venue_config)
    summary = chart_brief.get('summary', {})
    notables = chart_brief.get('notables', {})
    week_id = chart_brief.get('week_id')
    number_one = notables.get('number_one') or (tracks[0] if tracks else {})
    biggest_climber = (notables.get('biggest_climbers') or [{}])[0]
    new_entries = notables.get('new_entries') or []
    returning_tracks = notables.get('returning_tracks') or []
    longest_runner = max(tracks, key=lambda item: int(item.get('weeks_on_chart') or 0), default={})
    different_artists = len({track.get('artist') or track.get('track') for track in tracks if track.get('artist') or track.get('track')})

    rows = '\n'.join(render_asset_chart_row(track) for track in tracks)
    talk_cards = '\n'.join([
        render_asset_talk_card('🏆', 'Chart Leader', f"{track_label(number_one) or 'This week'} leads the Muddy's Top 10."),
        render_asset_talk_card('UP', 'Biggest Climber', (
            f"{track_label(biggest_climber)} climbs {biggest_climber.get('movement_delta')} places."
            if biggest_climber.get('track') else 'No major climber this week.'
        )),
        render_asset_talk_card('NEW', 'New Energy', (
            f"{len(new_entries)} new entr{'y' if len(new_entries) == 1 else 'ies'} hit the Top 10."
            if new_entries else 'No brand-new tracks this week.'
        )),
        render_asset_talk_card('WK', 'Chart Run', (
            f"{track_label(longest_runner)} leads the long-run story with {longest_runner.get('weeks_on_chart')} weeks."
            if longest_runner.get('track') and longest_runner.get('weeks_on_chart') else 'The chart keeps moving week on week.'
        )),
        render_asset_talk_card('2X', 'Returning Tracks', (
            f"{track_label(returning_tracks[0])} returns after last appearing {returning_tracks[0].get('last_seen_week')}."
            if returning_tracks else 'No returning tracks are called out this week.'
        )),
        render_asset_talk_card('♪', 'Chart Story', infographic.get('chart_story') or chart_story(chart_brief)),
    ])

    stats = {
        'new_entries': len(new_entries),
        'climbers': len([track for track in tracks if track.get('movement') == 'up']),
        'fallers': len([track for track in tracks if track.get('movement') == 'down']),
        'non_movers': len([track for track in tracks if track.get('movement') == 'same']),
        'total_plays': summary.get('total_plays') or sum(int(track.get('play_count') or 0) for track in tracks),
        'unique_tracks': summary.get('unique_tracks') or len(tracks),
        'history_weeks': summary.get('history_weeks_available') or 0,
        'different_artists': different_artists
    }

    template = infographic_template or resolve_template()
    html, css = render_template(template, {
        'MUDDYS_LOGO_DATA_URI': '{{MUDDYS_LOGO_DATA_URI}}',
        'LOGO_ALT': html_escape(branding.get('logo_alt', "Muddy's Music Cafe logo")),
        'CHART_TITLE': html_escape(branding.get('chart_title', "Muddy's Top 10")),
        'TAGLINE': html_escape(branding.get('tagline', 'Your requests. Your music. Your chart.')),
        'SUBHEAD': html_escape(infographic.get('subhead') or f'Week of {week_id}'),
        'CHART_ROWS': rows,
        'TALK_CARDS': talk_cards,
        'NEW_ENTRIES': html_escape(stats['new_entries']),
        'CLIMBERS': html_escape(stats['climbers']),
        'FALLERS': html_escape(stats['fallers']),
        'NON_MOVERS': html_escape(stats['non_movers']),
        'NUMBER_ONE_RANK': html_escape(number_one.get('rank', 1)),
        'NUMBER_ONE_ARTIST': html_escape(number_one.get('artist') or number_one.get('track') or 'this week'),
        'LONGEST_RUNNER_ARTIST': html_escape(longest_runner.get('artist') or longest_runner.get('track') or 'The chart'),
        'HISTORY_WEEKS': html_escape(stats['history_weeks']),
        'TOTAL_PLAYS': html_escape(stats['total_plays']),
        'UNIQUE_TRACKS': html_escape(stats['unique_tracks']),
        'DIFFERENT_ARTISTS': html_escape(stats['different_artists']),
        'COUNTDOWN_DAY': html_escape(venue.get('countdown_day', 'Every Saturday')),
        'COUNTDOWN_TIME': html_escape(venue.get('countdown_time', '2AM SLT')),
        'PRIMARY_COLOR': branding.get('primary_color', '#a855f7'),
        'SECONDARY_COLOR': branding.get('secondary_color', '#facc15'),
        'ACCENT_COLOR': branding.get('accent_color', '#d946ef'),
        'BACKGROUND_COLOR': branding.get('background_color', '#050005'),
        'TEXT_COLOR': branding.get('text_color', '#f8fafc'),
        'FONT_FAMILY_CSS': branding.get('font_family_css', "'Arial Narrow','Trebuchet MS',sans-serif")
    })

    return {
        'version': INFOGRAPHIC_ASSET_VERSION,
        'canvas': {
            'width': 1280,
            'height': 720
        },
        'metadata': {
            'week_id': week_id,
            'generated_at': utc_now_iso(),
            'source_snapshot_key': chart_brief.get('source_snapshot_key'),
            'design_summary': 'Stored campaign-specific authored HTML/CSS asset snapshot.',
            'template_id': template.get('template_id'),
            'template_version': template.get('version'),
            'template_source': template.get('source'),
            'template_reference_png_key': template_reference_metadata(template).get('s3_key'),
            'template_reference_png_generated_at': template_reference_metadata(template).get('generated_at'),
            'brand_config_snapshot': branding
        },
        'html': html,
        'css': css
    }


def generate_infographic_asset_with_model(
    chart_brief,
    infographic,
    venue_config,
    infographic_template,
    agent_spec,
    personal_context,
    memory_context,
    model_client,
    prompt_config=None,
    prompt_refs=None
):
    fallback = generate_infographic_asset(chart_brief, infographic, venue_config, infographic_template)
    prompt_package = build_infographic_asset_prompt_package(
        chart_brief,
        infographic,
        venue_config,
        infographic_template,
        agent_spec,
        personal_context,
        memory_context,
        INFOGRAPHIC_ASSET_SCHEMA,
        prompt_config=prompt_config
    )
    if prompt_refs is not None:
        prompt_refs['infographic_asset'] = prompt_package['ref']
    try:
        reference_images = infographic_template_reference_images(infographic_template)
        try:
            model_output = model_client.complete_text(prompt_package['text'], images=reference_images)
        except TypeError:
            model_output = model_client.complete_text(prompt_package['text'])
        generated = extract_infographic_asset_output(
            model_output
        )

        asset = {
            'version': INFOGRAPHIC_ASSET_VERSION,
            'canvas': {
                'width': 1280,
                'height': 720
            },
            'metadata': {
                **fallback.get('metadata', {}),
                **(generated.get('metadata') if isinstance(generated.get('metadata'), dict) else {}),
                'asset_generation_mode': 'model',
                'asset_model_endpoint': getattr(model_client, 'endpoint', 'bedrock-mantle'),
                'asset_model': getattr(model_client, 'model_id', None),
                'fallback_template_id': fallback.get('metadata', {}).get('template_id'),
                'fallback_template_version': fallback.get('metadata', {}).get('template_version')
            },
            'html': str(generated.get('html') or '').strip(),
            'css': str(generated.get('css') or '').strip(),
            'self_review': generated.get('self_review') if isinstance(generated.get('self_review'), dict) else {}
        }
        validation = validate_infographic_asset(asset, chart_brief)
        if not validation['valid']:
            raise ValueError('model-authored asset failed validation: ' + '; '.join(validation['errors']))
        return asset
    except Exception as e:
        fallback['metadata']['asset_generation_mode'] = 'template_fallback'
        fallback['metadata']['asset_model_endpoint'] = getattr(model_client, 'endpoint', 'bedrock-mantle')
        fallback['metadata']['asset_model'] = getattr(model_client, 'model_id', None)
        fallback['metadata']['model_error'] = str(e)
        return fallback


def build_infographic_asset_prompt_package(chart_brief, infographic, venue_config, infographic_template, agent_spec, personal_context, memory_context, schema, prompt_config=None):
    variables = prompt_variables(
        'infographic_asset',
        chart_brief,
        venue_config,
        agent_spec,
        personal_context,
        memory_context,
        schema,
        infographic=infographic,
        infographic_template=infographic_template
    )
    try:
        managed = render_managed_prompt('infographic_asset', prompt_config, variables)
        if managed:
            managed['text'] += infographic_asset_prompt_guard()
            return managed
    except Exception as e:
        print(f"Managed prompt unavailable for infographic_asset; using code prompt: {e}")
        return {
            'text': build_infographic_asset_prompt(chart_brief, infographic, venue_config, infographic_template, agent_spec, personal_context, memory_context, schema),
            'ref': {
                **code_prompt_ref('infographic_asset'),
                'fallback_reason': str(e)
            }
        }

    return {
        'text': build_infographic_asset_prompt(chart_brief, infographic, venue_config, infographic_template, agent_spec, personal_context, memory_context, schema),
        'ref': code_prompt_ref('infographic_asset')
    }


def build_infographic_asset_prompt(chart_brief, infographic, venue_config, infographic_template, agent_spec, personal_context, memory_context, schema):
    context_text = '\n\n'.join(item['content'] for item in personal_context)
    memory_text = campaign_json_dumps(memory_context, indent=2) if memory_context else '(none available)'
    branding = (venue_config.get('venue') or {}).get('branding', {})
    reference_image = infographic_template.get('reference_image') if isinstance(infographic_template, dict) else None
    reference_note = (
        "A rendered PNG reference image for the active template has been supplied as visual context. "
        "Respect its brand feel, density, hierarchy, and broadcast-poster intent, but adapt the final composition to this week's chart story. "
        "Do not trace it slavishly and do not ignore factual chart data.\n"
        if isinstance(reference_image, dict) and reference_image.get('data_uri')
        else "No rendered template reference PNG is available yet; rely on the starting template HTML/CSS and brand config.\n"
    )
    return (
        "You are authoring the final Muddy's Top 10 infographic HTML/CSS asset.\n"
        "Return exactly two fenced code blocks: one ```html block and one ```css block.\n"
        "Do not return JSON. Do not escape the HTML/CSS as string data.\n"
        "Do not include commentary before, between, or after the code blocks.\n"
        "Do not return image prompts. Do not describe a design for a later model. Create the actual HTML/CSS.\n"
        "The final render target is exactly 1280x720.\n"
        "Use selectable/rendered HTML text for all chart wording.\n"
        "Use the {{MUDDYS_LOGO_DATA_URI}} placeholder for the Muddy's logo.\n"
        "Do not include JavaScript, event handlers, iframes, forms, external URLs, remote fonts, external CSS, or external images.\n"
        "Logo, chart title, and tag line are non-negotiable and must appear exactly, allowing normal HTML escaping.\n"
        "Use the supplied colour/font tokens creatively but do not replace the palette.\n"
        "Use the supplied template as a starting design language, not a rigid fill-in form.\n"
        "You may change layout hierarchy, spacing, callouts, icon treatment, panels, and emphasis where the current chart story supports it.\n"
        "Facts in chart_brief are authoritative. Do not invent ranks, movement, play counts, dates, weeks on chart, or artist history.\n\n"
        f"TEMPLATE REFERENCE IMAGE:\n{reference_note}"
        f"REFERENCE IMAGE METADATA:\n{campaign_json_dumps(template_reference_metadata(infographic_template), indent=2)}\n\n"
        f"NON-NEGOTIABLE BRAND JSON:\n{campaign_json_dumps(branding, indent=2)}\n\n"
        f"AGENT SPEC:\n{agent_spec['content']}\n\n"
        f"PERSONAL CONTEXT:\n{context_text or '(none supplied)'}\n\n"
        f"AGENTCORE MEMORY CONTEXT:\n{memory_text}\n\n"
        f"VENUE CONFIG JSON:\n{campaign_json_dumps(venue_config, indent=2)}\n\n"
        f"CHART BRIEF JSON:\n{campaign_json_dumps(chart_brief, indent=2)}\n\n"
        f"INFOGRAPHIC CONTENT JSON:\n{campaign_json_dumps(infographic or {}, indent=2)}\n\n"
        f"STARTING TEMPLATE METADATA:\n{campaign_json_dumps({k: v for k, v in infographic_template.items() if k not in {'html', 'css'}}, indent=2)}\n\n"
        f"STARTING TEMPLATE HTML:\n{infographic_template.get('html', '')}\n\n"
        f"STARTING TEMPLATE CSS:\n{infographic_template.get('css', '')}\n\n"
        "OUTPUT FORMAT:\n"
        "```html\n<section class=\"poster\">...</section>\n```\n"
        "```css\n.poster { ... }\n```\n"
    )


def infographic_template_reference_images(infographic_template):
    reference = infographic_template.get('reference_image') if isinstance(infographic_template, dict) else None
    if not isinstance(reference, dict) or not reference.get('data_uri'):
        return []
    return [{
        'type': 'input_image',
        'image_url': reference['data_uri'],
        's3_key': reference.get('key'),
        'content_type': reference.get('content_type') or 'image/png'
    }]


def template_reference_metadata(infographic_template):
    reference = infographic_template.get('reference_image') if isinstance(infographic_template, dict) else None
    if not isinstance(reference, dict):
        return {'available': False}
    return {
        'available': bool(reference.get('data_uri')),
        's3_key': reference.get('key'),
        'content_type': reference.get('content_type') or 'image/png',
        'generated_at': reference.get('generated_at') or infographic_template.get('reference_png_generated_at')
    }


def render_asset_chart_row(track):
    movement = track.get('movement') or 'new'
    artist = clean_track_display(track.get('artist'))
    title = clean_track_display(track.get('title'))
    if not artist or not title:
        label = track_label(track)
        if ' - ' in label:
            artist, title = [part.strip() for part in label.split(' - ', 1)]
        else:
            title = title or label
    return (
        f'<li class="move-{html_escape(movement)}">'
        f'<b>{html_escape(str(track.get("rank", "")))}</b>'
        f'<span class="artist">{html_escape(artist or "Unknown Artist")}</span>'
        f'<span class="title">{html_escape(title or track_label(track))}</span>'
        f'<em>{html_escape(str(track.get("play_count", 0)))} plays</em>'
        f'<strong>{html_escape(asset_movement_label(track))}</strong>'
        '</li>'
    )


def render_asset_talk_card(icon, heading, body):
    return (
        '<article>'
        f'<b>{html_escape(icon)}</b>'
        f'<div><h3>{html_escape(heading)}</h3><p>{html_escape(body)}</p></div>'
        '</article>'
    )


def asset_movement_label(track):
    movement = track.get('movement')
    delta = track.get('movement_delta')
    if movement == 'up':
        return f"UP {abs(int(delta or 0))}"
    if movement == 'down':
        return f"DOWN {abs(int(delta or 0))}"
    if movement == 'same':
        return 'SAME'
    if track.get('last_seen_week') or movement == 'reentry':
        return 'RE-ENTRY'
    return 'NEW'


def html_escape(value):
    return (
        str(value)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;')
    )


def infographic_asset_css(branding=None):
    branding = normalize_campaign_branding(branding)
    primary = branding['primary_color']
    secondary = branding['secondary_color']
    accent = branding['accent_color']
    background = branding['background_color']
    text = branding['text_color']
    font_family = branding['font_family_css']
    return f"""
.poster{{width:1280px;height:720px;padding:14px 18px;background:radial-gradient(circle at 80% 0%,{accent}59,transparent 18%),radial-gradient(circle at 45% 80%,{primary}6b,transparent 24%),linear-gradient(135deg,{background},#10051f 48%,#020617);color:{text};font-family:{font_family};text-transform:uppercase;position:relative;overflow:hidden}}.poster:before{{content:"";position:absolute;inset:0;background:linear-gradient(transparent 95%,{primary}33),repeating-linear-gradient(90deg,transparent 0 78px,{primary}14 79px 80px);opacity:.5;pointer-events:none}}.masthead{{height:110px;display:grid;grid-template-columns:118px 1fr 340px;gap:18px;align-items:center;border-bottom:2px solid {primary};position:relative;z-index:1}}.logo{{width:110px;height:110px;object-fit:contain;filter:drop-shadow(0 0 10px {secondary})}}h1{{margin:0;font-size:52px;line-height:.88;letter-spacing:.035em;text-shadow:0 3px 0 #000,0 0 18px {primary}73}}h1 span{{color:{primary}}}.title-block p{{margin:0 0 0 72px;color:{secondary};font-family:'Brush Script MT',cursive;font-size:34px;text-transform:none}}.date-block{{text-align:right;border-top:3px solid {secondary};border-bottom:3px solid {secondary};padding:8px 0}}.date-block strong{{display:block;font-size:23px}}.date-block small{{display:block;font-size:13px;line-height:1.25;color:#e5e7eb}}.main-grid{{display:grid;grid-template-columns:728px 1fr;gap:12px;margin-top:9px;position:relative;z-index:1}}.chart-panel{{height:350px;border:1px solid {primary};background:linear-gradient(90deg,rgba(9,0,18,.95),rgba(9,0,18,.72));box-shadow:0 0 24px {primary}2e}}.chart-heading{{height:25px;display:grid;grid-template-columns:56px 190px 1fr 70px 116px;align-items:center;color:{secondary};font-size:13px;letter-spacing:.08em;border-bottom:1px solid {primary}a6;padding-right:8px}}.chart-heading span{{padding-left:10px}}.chart{{list-style:none;margin:0;padding:0}}.chart li{{height:32.4px;display:grid;grid-template-columns:56px 190px 1fr 70px 116px;align-items:center;border-bottom:1px solid {primary}57}}.chart li:last-child{{border-bottom:0}}.chart b{{height:100%;display:grid;place-items:center;background:linear-gradient(135deg,{primary},#4c1d95);font-size:30px;color:#fff}}.chart span{{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:900}}.chart .artist{{padding-left:12px;color:{text};font-size:21px}}.chart .title{{color:#e5e7eb;font-size:20px;text-transform:none}}.chart em{{color:{primary};font-style:normal;font-size:15px;font-weight:900}}.chart strong{{font-size:14px;text-align:center;color:{secondary}}}.chart .move-up strong{{color:#22c55e}}.chart .move-down strong{{color:#ef4444}}.chart .move-same strong{{color:#d1d5db}}.talk{{height:350px;border:1px solid {secondary};background:rgba(0,0,0,.74);padding:35px 14px 12px;display:grid;grid-template-columns:1fr 1fr;gap:8px;position:relative;box-shadow:0 0 24px {secondary}21}}.talk h2{{position:absolute;top:-17px;left:50%;transform:translateX(-50%) skew(-8deg);margin:0;background:{secondary};color:#020617;padding:5px 42px;font-size:27px;font-style:italic;box-shadow:0 4px 0 rgba(0,0,0,.55)}}.talk article{{display:grid;grid-template-columns:42px 1fr;gap:9px;border-bottom:1px dotted rgba(255,255,255,.42);padding:7px}}.talk article b{{width:36px;height:36px;border:1px solid {accent};border-radius:999px;display:grid;place-items:center;color:{secondary};font-size:15px}}.talk h3{{margin:0 0 4px;color:{secondary};font-size:16px}}.talk p{{margin:0;color:#e5e7eb;font-size:12.5px;line-height:1.18;text-transform:none;font-weight:800}}.stats{{height:105px;margin-top:9px;border:1px solid {primary};background:rgba(0,0,0,.75);display:grid;grid-template-columns:.82fr 1.16fr .98fr;position:relative;z-index:1}}.stats article{{padding:9px 13px;border-right:1px solid {primary}8c}}.stats article:last-child{{border-right:0}}.stats h3{{margin:0 0 5px;color:{secondary};font-size:15px}}.stats p{{margin:0;color:#e5e7eb;font-size:12px;line-height:1.35}}.stats b{{color:{secondary};font-size:17px}}.footer{{height:92px;margin-top:8px;display:grid;grid-template-columns:240px 265px 1fr 112px;gap:16px;align-items:center;position:relative;z-index:1}}.footer small{{display:block;color:#d1d5db;font-size:15px}}.footer strong{{display:block;color:{secondary};font-size:22px}}.footer em{{display:block;color:{secondary};font-family:'Brush Script MT',cursive;font-size:18px;text-transform:none}}.venue{{text-align:center;color:#22c55e;font-size:23px;font-weight:900}}.venue strong{{display:block;color:{text};font-size:28px}}.venue span{{display:block;color:{accent};font-size:13px;letter-spacing:.08em}}.badge{{width:104px;height:104px;border:2px solid {accent};border-radius:999px;display:grid;place-items:center;text-align:center;color:{text};font-size:12px;line-height:1.15;box-shadow:0 0 18px {accent}d9;text-transform:none}}.badge b{{color:{secondary}}}.strap{{position:absolute;left:0;right:0;bottom:6px;text-align:center;color:#cbd5e1;font-size:13px;letter-spacing:.08em;z-index:1}}.strap b{{color:{accent}}}
""".strip()


def generate_infographic_content_with_model(chart_brief, venue_config, agent_spec, personal_context, memory_context, model_client, prompt_config=None, prompt_refs=None):
    fallback = generate_infographic_content(chart_brief, venue_config)
    return generate_section_with_model(
        'infographic',
        chart_brief,
        venue_config,
        agent_spec,
        personal_context,
        memory_context,
        model_client,
        fallback,
        INFOGRAPHIC_SCHEMA,
        prompt_config=prompt_config,
        prompt_refs=prompt_refs
    )


def generate_social_posts(chart_brief, venue_config=None):
    venue = (venue_config or DEFAULT_VENUE_CONFIG)['venue']
    story = chart_story(chart_brief)
    top = (chart_brief.get('tracks') or [{}])[0]
    week_id = chart_brief.get('week_id')
    tracks = chart_brief.get('tracks', [])[:10]
    top_three = ', '.join(track_label(track) for track in tracks[:3])
    movement = _movement_summary(chart_brief)
    location_line = social_location_line(venue)

    return {
        'facebook': {
            'post': (
                f"🎶 This week's Muddy's Top 10 is ready for week {week_id}.\n\n"
                f"{story}\n\n"
                f"🏆 Your Top 3: {top_three}.\n\n"
                f"📈 {movement}\n\n"
                f"🎧 Catch the countdown at {venue.get('countdown_time')} on {venue.get('countdown_day')} with DJ Toohey & JP.\n\n"
                f"{location_line}"
            ),
            'hashtags': ['#MuddysMusicCafe', '#SecondLife', '#Top10']
        },
        'primfeed': {
            'post': (
                f"🎵 Muddy's Top 10 for week {week_id} is live.\n\n"
                f"🏆 #1: {track_label(top) or 'TBA'}\n"
                f"🔥 Top 3: {top_three}.\n"
                f"📊 {movement}\n\n"
                f"Come see what moved, what held, and what broke through at {venue.get('name')}.\n\n"
                f"{location_line}"
            ),
            'hashtags': ['#MuddysMusicCafe', '#SecondLife', '#SLMusic']
        },
        'discord': {
            'post': (
                f"📣 **Muddy's Top 10 for {week_id} is in.**\n"
                f"{story}\n"
                f"🏆 Top 3: {top_three}.\n"
                f"📈 {movement}\n\n"
                f"{location_line}"
            )
        },
        'teaser': {
            'short_copy': f"🎶 New Muddy's Top 10: #{top.get('rank', 1)} {track_label(top) or 'TBA'} leads this week's chart."
        },
        'alt_text': f"Infographic for the Muddy's Top 10 chart, week of {week_id}.",
        'self_review': {
            'facts_verified': True,
            'pg_appropriate': True,
            'missing_inputs': validate_chart_brief(chart_brief)
        }
    }


def social_location_line(venue):
    slurl = venue.get('slurl') or venue.get('surl') or venue.get('location_url')
    venue_name = venue.get('name', "Muddy's Music Cafe")
    if not slurl:
        return f"📍 Join us at {venue_name} in {venue.get('world', 'Second Life')}."
    return f"📍 Join us at {venue_name}: {slurl}"


def generate_social_posts_with_model(chart_brief, venue_config, agent_spec, personal_context, memory_context, model_client, prompt_config=None, prompt_refs=None):
    fallback = generate_social_posts(chart_brief, venue_config)
    return generate_section_with_model(
        'social',
        chart_brief,
        venue_config,
        agent_spec,
        personal_context,
        memory_context,
        model_client,
        fallback,
        SOCIAL_SCHEMA,
        prompt_config=prompt_config,
        prompt_refs=prompt_refs
    )


def create_campaign_draft(chart_brief, sections=None, venue_config=None, infographic_template=None, prompt_config=None, requested_by=None, generated_by='scheduled-agent'):
    sections = sections or ['radio', 'infographic', 'social']
    venue_config = venue_config or venue_config_with_branding()
    prompt_config = normalize_prompt_config(prompt_config)
    prompt_refs = {}
    agent_specs = load_agent_specs()
    personal_context = load_personal_context()
    memory_context = retrieve_campaign_memory(chart_brief)
    model_client = BedrockCampaignModel.from_env()

    draft = {
        'pk': 'CAMPAIGN',
        'sk': f"WEEK#{chart_brief['week_id']}",
        'week_id': chart_brief['week_id'],
        'status': 'draft',
        'chart_brief': chart_brief,
        'generated_at': utc_now_iso(),
        'generated_by': generated_by,
        'requested_by': requested_by,
        'source_snapshot_key': chart_brief.get('source_snapshot_key'),
        'generator': {
            'mode': campaign_generation_mode(model_client),
            'model': model_client.model_id if model_client else None,
            'model_endpoint': getattr(model_client, 'endpoint', 'bedrock-mantle') if model_client else None,
            'prompt_version': 'agentic-campaign-v1',
            'prompt_refs': prompt_refs,
            'agent_spec_versions': {
                name: spec['sha256'] for name, spec in agent_specs.items()
            },
            'context_refs': context_refs(agent_specs, personal_context),
            'memory_enabled': bool(os.environ.get('AGENTCORE_MEMORY_ID', '').strip()),
            'memory_records_used': len(memory_context)
        },
        'memory_refs': memory_context,
        'review': {},
        'regeneration_count': 0
    }

    if 'radio' in sections:
        if model_client and agent_specs.get('radio'):
            draft['radio_reads'] = generate_radio_reads_with_model(
                chart_brief,
                venue_config,
                agent_specs['radio'],
                personal_context,
                memory_context,
                model_client,
                prompt_config=prompt_config,
                prompt_refs=prompt_refs
            )
        else:
            draft['radio_reads'] = generate_radio_reads(chart_brief, venue_config)
    if 'infographic' in sections:
        if model_client and agent_specs.get('infographic'):
            draft['infographic'] = generate_infographic_content_with_model(
                chart_brief,
                venue_config,
                agent_specs['infographic'],
                personal_context,
                memory_context,
                model_client,
                prompt_config=prompt_config,
                prompt_refs=prompt_refs
            )
        else:
            draft['infographic'] = generate_infographic_content(chart_brief, venue_config)
        if model_client and agent_specs.get('infographic'):
            draft['infographic_asset'] = generate_infographic_asset_with_model(
                chart_brief,
                draft.get('infographic'),
                venue_config,
                infographic_template or resolve_template(),
                agent_specs['infographic'],
                personal_context,
                memory_context,
                model_client,
                prompt_config=prompt_config,
                prompt_refs=prompt_refs
            )
        else:
            draft['infographic_asset'] = generate_infographic_asset(
                chart_brief,
                draft.get('infographic'),
                venue_config,
                infographic_template
            )
        draft['infographic_asset_validation'] = validate_infographic_asset(
            draft['infographic_asset'],
            chart_brief
        )
        if not draft['infographic_asset_validation']['valid']:
            draft['status'] = 'failed'
            draft['failure'] = {
                'reason': 'invalid_infographic_asset',
                'errors': draft['infographic_asset_validation']['errors']
            }
    if 'social' in sections:
        if model_client and agent_specs.get('social'):
            draft['social'] = generate_social_posts_with_model(
                chart_brief,
                venue_config,
                agent_specs['social'],
                personal_context,
                memory_context,
                model_client,
                prompt_config=prompt_config,
                prompt_refs=prompt_refs
            )
        else:
            draft['social'] = generate_social_posts(chart_brief, venue_config)

    missing_inputs = sorted(set(
        missing
        for section in ('radio_reads', 'infographic', 'social')
        for missing in draft.get(section, {}).get('self_review', {}).get('missing_inputs', [])
    ))
    if missing_inputs:
        draft['status'] = 'failed'
        draft['failure'] = {
            'reason': 'missing_required_inputs',
            'missing_inputs': missing_inputs
        }

    memory_event_id = remember_campaign(draft)
    if memory_event_id:
        draft['generator']['memory_event_id'] = memory_event_id

    return draft


def campaign_generation_mode(model_client):
    if not model_client:
        return 'deterministic-draft-v1'
    endpoint = getattr(model_client, 'endpoint', 'bedrock-mantle')
    if endpoint == 'strands-openai-responses':
        return 'strands-openai-responses-v1'
    if endpoint == 'bedrock-runtime':
        return 'bedrock-runtime-json-v1'
    return 'bedrock-mantle-json-v1'


class BedrockCampaignModel:
    def __init__(
        self,
        model_id,
        endpoint='bedrock-mantle',
        max_tokens=1800,
        temperature=0.4,
        client=None,
        project_id=None,
        read_timeout=120,
        api_key_secret_arn=None
    ):
        self.model_id = model_id
        self.endpoint = endpoint
        self.max_tokens = int(max_tokens)
        self.temperature = float(temperature)
        self.client = client
        self.project_id = project_id
        self.read_timeout = float(read_timeout)
        self.api_key_secret_arn = api_key_secret_arn
        self._api_key = None

    @classmethod
    def from_env(cls):
        model_id = os.environ.get('CAMPAIGN_MODEL_ID', '').strip()
        if not model_id:
            return None
        return cls(
            model_id=model_id,
            endpoint=os.environ.get('CAMPAIGN_MODEL_ENDPOINT', 'bedrock-mantle'),
            max_tokens=os.environ.get('CAMPAIGN_MODEL_MAX_TOKENS', '1800'),
            temperature=os.environ.get('CAMPAIGN_MODEL_TEMPERATURE', '0.4'),
            project_id=os.environ.get('CAMPAIGN_MODEL_PROJECT_ID', '').strip() or None,
            read_timeout=os.environ.get('CAMPAIGN_MODEL_READ_TIMEOUT_SECONDS', '120'),
            api_key_secret_arn=os.environ.get('CAMPAIGN_MODEL_API_KEY_SECRET_ARN', '').strip() or None
        )

    def complete_json(self, prompt):
        return extract_json_object(self.complete_text(prompt, response_format='json_object'))

    def complete_text(self, prompt, response_format=None, images=None):
        if self.endpoint == 'strands-openai-responses':
            return self.complete_text_with_strands_openai_responses(prompt, response_format=response_format, images=images)
        if self.endpoint == 'bedrock-mantle':
            return self.complete_text_with_mantle(prompt, response_format=response_format)
        return self.complete_text_with_bedrock_runtime(prompt)

    def complete_text_with_strands_openai_responses(self, prompt, response_format=None, images=None):
        try:
            from strands import Agent
            from strands.models.openai_responses import OpenAIResponsesModel
        except Exception as e:
            raise RuntimeError(f'Strands OpenAI Responses provider is not available: {e}')

        api_key = self.model_api_key()
        region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-west-2'
        base_url = os.environ.get(
            'CAMPAIGN_MODEL_BASE_URL',
            f'https://bedrock-mantle.{region}.api.aws/v1'
        ).rstrip('/')
        headers = {}
        if self.project_id:
            headers['OpenAI-Project'] = self.project_id
        client_args = {
            'api_key': api_key,
            'base_url': base_url,
            'timeout': self.read_timeout
        }
        if headers:
            client_args['default_headers'] = headers
        params = {
            'temperature': self.temperature,
            'max_output_tokens': self.max_tokens
        }
        if response_format == 'json_object':
            params['text'] = {'format': {'type': 'json_object'}}
        model = OpenAIResponsesModel(
            model_id=self.model_id,
            client_args=client_args,
            params=params
        )
        agent = Agent(model=model)
        if images:
            image_parts = [
                {'type': 'input_text', 'text': prompt},
                *[
                    {'type': 'input_image', 'image_url': image['image_url']}
                    for image in images
                    if isinstance(image, dict) and image.get('image_url')
                ]
            ]
            try:
                return extract_agent_text(agent(image_parts))
            except Exception as e:
                print(f"Strands multimodal campaign request failed; retrying without image reference: {e}")
        return extract_agent_text(agent(prompt))

    def model_api_key(self):
        if self._api_key:
            return self._api_key
        if not self.api_key_secret_arn:
            raise RuntimeError('CAMPAIGN_MODEL_API_KEY_SECRET_ARN is required for strands-openai-responses')
        import boto3
        secret = boto3.client('secretsmanager').get_secret_value(SecretId=self.api_key_secret_arn)
        value = secret.get('SecretString') or ''
        try:
            parsed = json.loads(value)
            value = parsed.get('api_key') or parsed.get('bedrock_api_key') or parsed.get('key') or value
        except json.JSONDecodeError:
            pass
        self._api_key = str(value).strip()
        if not self._api_key:
            raise RuntimeError('Campaign model API key secret is empty')
        return self._api_key

    def complete_text_with_bedrock_runtime(self, prompt):
        if self.client is None:
            import boto3
            from botocore.config import Config
            self.client = boto3.client(
                'bedrock-runtime',
                config=Config(connect_timeout=10, read_timeout=int(self.read_timeout), retries={'max_attempts': 0})
            )

        body = {
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': prompt
                        }
                    ]
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(body)
        )
        payload = json.loads(response['body'].read().decode('utf-8'))
        text = ''.join(
            block.get('text', '')
            for block in payload.get('content', [])
            if block.get('type') == 'text'
        )
        return text

    def complete_text_with_mantle(self, prompt, response_format=None):
        import urllib3
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        from botocore.session import Session

        region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-west-2'
        base_url = os.environ.get(
            'CAMPAIGN_MODEL_BASE_URL',
            f'https://bedrock-mantle.{region}.api.aws/v1'
        ).rstrip('/')
        url = f'{base_url}/chat/completions'
        body = json.dumps({
            'model': self.model_id,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature
        })
        body_data = json.loads(body)
        if response_format:
            body_data['response_format'] = {'type': response_format}
            body = json.dumps(body_data)

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.project_id:
            headers['OpenAI-Project'] = self.project_id
        request = AWSRequest(method='POST', url=url, data=body, headers=headers)
        credentials = Session().get_credentials()
        if credentials is None:
            raise RuntimeError('AWS credentials are not available for Bedrock Mantle request signing')
        SigV4Auth(credentials.get_frozen_credentials(), 'bedrock-mantle', region).add_auth(request)

        http = urllib3.PoolManager()
        response = http.request(
            'POST',
            url,
            body=body,
            headers=dict(request.headers),
            timeout=urllib3.Timeout(connect=5.0, read=self.read_timeout)
        )
        if response.status >= 300:
            raise RuntimeError(f'Bedrock Mantle request failed with HTTP {response.status}: {response.data.decode("utf-8")}')

        payload = json.loads(response.data.decode('utf-8'))
        choices = payload.get('choices') or []
        if not choices:
            raise RuntimeError('Bedrock Mantle response did not include choices')
        message = choices[0].get('message') or {}
        content = message.get('content')
        if isinstance(content, list):
            text = ''.join(item.get('text', '') for item in content if isinstance(item, dict))
        else:
            text = content or ''
        return text


def generate_section_with_model(
    section_name,
    chart_brief,
    venue_config,
    agent_spec,
    personal_context,
    memory_context,
    model_client,
    fallback,
    schema,
    prompt_config=None,
    prompt_refs=None
):
    prompt_package = build_generation_prompt_package(
        section_name,
        chart_brief,
        venue_config,
        agent_spec,
        personal_context,
        memory_context,
        schema,
        prompt_config=prompt_config
    )
    if prompt_refs is not None:
        prompt_refs[section_name] = prompt_package['ref']
    try:
        generated = model_client.complete_json(prompt_package['text'])
        if not isinstance(generated, dict):
            raise ValueError('model output was not a JSON object')
        generated.setdefault('self_review', {})
        generated['self_review'].setdefault('facts_verified', True)
        generated['self_review'].setdefault('missing_inputs', validate_chart_brief(chart_brief))
        generated['generation_mode'] = 'model'
        return enforce_section_quality(section_name, generated, fallback)
    except Exception as e:
        print(f"Model generation failed for {section_name}; using deterministic fallback: {e}")
        fallback['generation_mode'] = 'deterministic_fallback'
        fallback['model_error'] = str(e)
        return fallback


def enforce_section_quality(section_name, generated, fallback):
    if section_name == 'radio_reads':
        position_reads = generated.get('position_reads')
        if not isinstance(position_reads, list) or len(position_reads) < 10:
            generated['position_reads'] = fallback.get('position_reads', [])
            generated['generation_mode'] = 'model_with_deterministic_position_reads'
        for key in ('intro', 'top10_intro', 'top5_recap', 'top3_recap', 'outro'):
            if not generated.get(key):
                generated[key] = fallback.get(key)

    if section_name == 'infographic':
        for key in ('headline', 'subhead', 'chart_story', 'movement_summary', 'statistics', 'track_cards', 'promotional_footer'):
            value = generated.get(key)
            if value in (None, '', [], {}):
                generated[key] = fallback.get(key)
                generated['generation_mode'] = 'model_with_deterministic_infographic_fields'

    if section_name == 'social':
        for key in ('facebook', 'primfeed', 'discord', 'teaser', 'alt_text'):
            value = generated.get(key)
            if value in (None, '', [], {}):
                generated[key] = fallback.get(key)
                generated['generation_mode'] = 'model_with_deterministic_social_fields'

        generated = repair_social_posts(generated, fallback)
        facebook_post = ((generated.get('facebook') or {}).get('post') or '').strip()
        if len(facebook_post) < 180:
            generated['facebook'] = fallback.get('facebook')
            generated['generation_mode'] = 'model_with_deterministic_social_fields'

    return generated


def repair_social_posts(generated, fallback):
    top_fallback = ((fallback.get('teaser') or {}).get('short_copy') or '').strip()

    for channel in ('facebook', 'primfeed', 'discord'):
        value = generated.get(channel)
        fallback_value = fallback.get(channel)
        if not isinstance(value, dict):
            continue

        post = str(value.get('post') or value.get('copy') or '').strip()
        if not post:
            generated[channel] = fallback_value
            generated['generation_mode'] = 'model_with_deterministic_social_fields'
            continue

        repaired = repair_blank_rank_phrases(post)
        if social_post_lost_number_one_fact(repaired, top_fallback):
            generated[channel] = fallback_value
            generated['generation_mode'] = 'model_with_deterministic_social_fields'
            continue

        value['post'] = repaired

    return generated


def repair_blank_rank_phrases(post):
    repaired = re.sub(r'\bat\s+(?:#\s*)?with\b', 'at number one with', post, flags=re.IGNORECASE)
    repaired = re.sub(r'\bto\s+(?:#\s*)?with\b', 'to number one with', repaired, flags=re.IGNORECASE)
    repaired = re.sub(r'\bholds\s+(?:#\s*)?with\b', 'holds number one with', repaired, flags=re.IGNORECASE)
    return repaired


def social_post_lost_number_one_fact(post, fallback_teaser):
    if not fallback_teaser:
        return False
    match = re.search(r'#1\s+(.+?)\s+leads this week', fallback_teaser)
    if not match:
        return False
    top_track = clean_track_display(match.group(1))
    if not top_track:
        return False
    parts = [part.strip().lower() for part in top_track.split(' - ', 1) if part.strip()]
    post_lower = post.lower()
    return any(part and part not in post_lower for part in parts)


def build_generation_prompt_package(section_name, chart_brief, venue_config, agent_spec, personal_context, memory_context, schema, prompt_config=None):
    variables = prompt_variables(
        section_name,
        chart_brief,
        venue_config,
        agent_spec,
        personal_context,
        memory_context,
        schema
    )
    try:
        managed = render_managed_prompt(section_name, prompt_config, variables)
        if managed:
            managed['text'] += managed_prompt_guard(schema)
            return managed
    except Exception as e:
        print(f"Managed prompt unavailable for {section_name}; using code prompt: {e}")
        return {
            'text': build_generation_prompt(section_name, chart_brief, venue_config, agent_spec, personal_context, memory_context, schema),
            'ref': {
                **code_prompt_ref(section_name),
                'fallback_reason': str(e)
            }
        }

    return {
        'text': build_generation_prompt(section_name, chart_brief, venue_config, agent_spec, personal_context, memory_context, schema),
        'ref': code_prompt_ref(section_name)
    }


def build_generation_prompt(section_name, chart_brief, venue_config, agent_spec, personal_context, memory_context, schema):
    context_text = '\n\n'.join(item['content'] for item in personal_context)
    memory_text = campaign_json_dumps(memory_context, indent=2) if memory_context else '(none available)'
    return (
        "You generate one section of a weekly Muddy's Top 10 campaign.\n"
        "Return only valid JSON. Do not wrap the JSON in markdown.\n"
        "The output must be production-useful, not placeholder notes or vague directions.\n"
        "For radio_reads, provide all 10 position_reads with substantive readout text.\n"
        "For infographic, provide useful chart_story, movement_summary, statistics, and all 10 track_cards; the system will render the final branded PNG from these facts.\n"
        "For social, write complete channel-ready posts, not disconnected one-liners. Always include the current number-one track with its rank, artist, and title; never leave a blank rank or blank chart position. If venue.slurl, venue.surl, or venue.location_url is present, include it as the public Second Life destination URL.\n"
        "Facts in chart_brief are authoritative. Do not invent chart facts, artist history, rankings, play counts, or movement.\n"
        "Use AgentCore memory only for editorial continuity, recurring preferences, and avoiding stale repetition.\n"
        "Do not let memory override the current chart_brief facts.\n"
        "If required data is missing, include it in self_review.missing_inputs instead of guessing.\n\n"
        f"SECTION:\n{section_name}\n\n"
        f"AGENT SPEC:\n{agent_spec['content']}\n\n"
        f"PERSONAL CONTEXT:\n{context_text or '(none supplied)'}\n\n"
        f"AGENTCORE MEMORY CONTEXT:\n{memory_text}\n\n"
        f"VENUE CONFIG JSON:\n{campaign_json_dumps(venue_config, indent=2)}\n\n"
        f"CHART BRIEF JSON:\n{campaign_json_dumps(chart_brief, indent=2)}\n\n"
        f"OUTPUT JSON SHAPE:\n{campaign_json_dumps(schema, indent=2)}\n"
    )


def prompt_variables(section_name, chart_brief, venue_config, agent_spec, personal_context, memory_context, schema, infographic=None, infographic_template=None):
    context_text = '\n\n'.join(item['content'] for item in personal_context)
    memory_text = campaign_json_dumps(memory_context, indent=2) if memory_context else '(none available)'
    variables = {
        'section_name': section_name,
        'agent_spec': agent_spec.get('content', ''),
        'personal_context': context_text or '(none supplied)',
        'memory_context': memory_text,
        'venue_config_json': campaign_json_dumps(venue_config, indent=2),
        'chart_brief_json': campaign_json_dumps(chart_brief, indent=2),
        'output_schema_json': campaign_json_dumps(schema, indent=2)
    }
    if infographic is not None:
        variables['infographic_json'] = campaign_json_dumps(infographic, indent=2)
    if infographic_template is not None:
        variables['template_metadata_json'] = campaign_json_dumps(
            {k: v for k, v in infographic_template.items() if k not in {'html', 'css'}},
            indent=2
        )
        variables['template_html'] = infographic_template.get('html', '')
        variables['template_css'] = infographic_template.get('css', '')
    return variables


def managed_prompt_guard(schema):
    return (
        "\n\nMANDATORY OUTPUT CONTRACT:\n"
        "Return only valid JSON. Do not wrap JSON in markdown. Do not invent chart facts.\n"
        f"Required JSON shape:\n{campaign_json_dumps(schema, indent=2)}\n"
    )


def infographic_asset_prompt_guard():
    return (
        "\n\nMANDATORY OUTPUT CONTRACT:\n"
        "Return exactly two fenced code blocks and nothing else.\n"
        "The first block must be ```html and contain the complete infographic HTML fragment.\n"
        "The second block must be ```css and contain the complete infographic CSS.\n"
        "Do not return JSON. Do not escape HTML/CSS into strings. Do not invent chart facts.\n"
    )


def campaign_json_dumps(value, **kwargs):
    return json.dumps(value, default=json_safe_default, **kwargs)


def json_safe_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f'Object of type {value.__class__.__name__} is not JSON serializable')


def extract_json_object(text):
    stripped = text.strip()
    if stripped.startswith('```'):
        stripped = stripped.strip('`')
        if stripped.lower().startswith('json'):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find('{')
        end = stripped.rfind('}')
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start:end + 1])


def extract_infographic_asset_output(text):
    stripped = (text or '').lstrip()
    if stripped.startswith('{') or stripped.startswith('```json'):
        parsed = extract_json_object(text)
        if isinstance(parsed, dict) and parsed.get('html') and parsed.get('css'):
            parsed.setdefault('metadata', {})
            parsed['metadata']['output_format'] = 'legacy_json_html_css'
            return parsed

    html = extract_fenced_block(text, 'html')
    css = extract_fenced_block(text, 'css')
    if not html or not css:
        generic_blocks = extract_generic_fenced_blocks(text)
        html = html or first_html_block(generic_blocks)
        css = css or first_css_block(generic_blocks)
    if not html or not css:
        labelled = extract_labelled_html_css(text)
        html = html or labelled.get('html', '')
        css = css or labelled.get('css', '')
    if not html or not css:
        raw = extract_raw_html_css(text)
        html = html or raw.get('html', '')
        css = css or raw.get('css', '')
    if html and css:
        return {
            'metadata': {
                'design_summary': 'Model-authored HTML/CSS extracted from generated code output.',
                'output_format': 'html_css_blocks'
            },
            'html': html,
            'css': css,
            'self_review': {
                'ready_for_render': True
            }
        }

    raise ValueError(f'model output did not contain extractable HTML/CSS blocks; output excerpt: {safe_excerpt(text)}')


def extract_fenced_block(text, language):
    pattern = rf'```{re.escape(language)}\s*\n(.*?)\n```'
    match = re.search(pattern, text or '', flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ''


def extract_generic_fenced_blocks(text):
    return [
        match.group(1).strip()
        for match in re.finditer(r'```\s*\n(.*?)\n```', text or '', flags=re.DOTALL)
    ]


def first_html_block(blocks):
    for block in blocks:
        if re.search(r'<(?:section|div|main|article|header)\b', block, flags=re.IGNORECASE):
            return block.strip()
    return ''


def first_css_block(blocks):
    for block in blocks:
        if re.search(r'(^|\n)\s*[.#a-zA-Z][^{]{0,80}\{', block):
            return block.strip()
    return ''


def extract_labelled_html_css(text):
    value = text or ''
    html_match = re.search(r'(?:^|\n)\s*(?:HTML|html)\s*:\s*\n(.*?)(?=\n\s*(?:CSS|css)\s*:|\Z)', value, flags=re.DOTALL)
    css_match = re.search(r'(?:^|\n)\s*(?:CSS|css)\s*:\s*\n(.*)\Z', value, flags=re.DOTALL)
    return {
        'html': html_match.group(1).strip() if html_match else '',
        'css': css_match.group(1).strip() if css_match else ''
    }


def extract_raw_html_css(text):
    value = text or ''
    html_match = re.search(r'(<(?:section|div|main)\b.*?</(?:section|div|main)>)', value, flags=re.IGNORECASE | re.DOTALL)
    css = ''
    if html_match:
        remainder = value[html_match.end():]
        css = re.sub(r'^\s*(?:CSS|css)\s*:?\s*', '', remainder).strip()
    return {
        'html': html_match.group(1).strip() if html_match else '',
        'css': css
    }


def safe_excerpt(text, limit=500):
    return re.sub(r'\s+', ' ', str(text or '')).strip()[:limit]


def extract_agent_text(result):
    if result is None:
        return ''
    if isinstance(result, str):
        return result
    for attr in ('message', 'content', 'text'):
        value = getattr(result, attr, None)
        text = extract_content_text(value)
        if text:
            return text
    if isinstance(result, dict):
        for key in ('message', 'content', 'text', 'output_text'):
            text = extract_content_text(result.get(key))
            if text:
                return text
    return str(result)


def extract_content_text(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.append(extract_content_text(item))
        return ''.join(parts)
    if isinstance(value, dict):
        if value.get('text'):
            return str(value.get('text'))
        if value.get('content'):
            return extract_content_text(value.get('content'))
    return ''


def merge_regenerated_sections(existing_campaign, regenerated_campaign, sections):
    updated = dict(existing_campaign)
    for section in sections:
        if section == 'radio' and 'radio_reads' in regenerated_campaign:
            updated['radio_reads'] = regenerated_campaign['radio_reads']
        elif section == 'infographic' and 'infographic' in regenerated_campaign:
            updated['infographic'] = regenerated_campaign['infographic']
            if 'infographic_asset' in regenerated_campaign:
                updated['infographic_asset'] = regenerated_campaign['infographic_asset']
            if 'infographic_asset_validation' in regenerated_campaign:
                updated['infographic_asset_validation'] = regenerated_campaign['infographic_asset_validation']
            updated.pop('infographic_png', None)
        elif section == 'social' and 'social' in regenerated_campaign:
            updated['social'] = regenerated_campaign['social']

    updated['status'] = 'draft'
    updated.pop('failure', None)
    updated['generated_at'] = regenerated_campaign['generated_at']
    updated['generated_by'] = regenerated_campaign['generated_by']
    updated['requested_by'] = regenerated_campaign.get('requested_by')
    updated['generator'] = regenerated_campaign['generator']
    updated['regeneration_count'] = int(existing_campaign.get('regeneration_count', 0)) + 1
    return updated


def _recap(tracks, label):
    if not tracks:
        return f"{label} is not available yet."
    rendered = ', '.join(f"#{track['rank']} {track['track']}" for track in tracks)
    return f"{label}: {rendered}."


def _movement_summary(chart_brief):
    notables = chart_brief.get('notables', {})
    new_count = len(notables.get('new_entries') or [])
    climbers = notables.get('biggest_climbers') or []
    drops = notables.get('biggest_drops') or []

    parts = []
    if new_count:
        parts.append(f"{new_count} new entr{'ies' if new_count != 1 else 'y'}")
    if climbers:
        parts.append(f"biggest climber: {climbers[0]['track']} ({movement_text(climbers[0])})")
    if drops:
        parts.append(f"biggest drop: {drops[0]['track']} ({movement_text(drops[0])})")
    return '; '.join(parts) if parts else 'A steady week across the chart.'


def _statistics(chart_brief):
    summary = chart_brief.get('summary', {})
    stats = []
    for key, label in (
        ('total_plays', 'total chart-eligible plays'),
        ('unique_tracks', 'unique chart-eligible tracks'),
        ('current_top10_count', 'tracks in the published chart')
    ):
        if summary.get(key) is not None:
            stats.append({'label': label, 'value': summary[key]})
    return stats
