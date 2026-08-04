"""Agentic campaign draft generation."""
import json
import os
import re
from copy import deepcopy
from decimal import Decimal
from datetime import datetime, timezone

from agent_context import context_refs, load_agent_specs, load_personal_context
from agent_memory import remember_campaign, retrieve_campaign_memory
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

# --- Section-specific context selection ---
# Maps each generation section to the context filenames relevant to it.
# Universal files are included in every section. Section-specific files
# are only included when generating that section, keeping prompts focused.
_UNIVERSAL_CONTEXT_FILES = {
    'personal-voice.md',
    'muddys-venue-context.md',
    'words-and-phrases.md',
    'never-say.md',
}

SECTION_CONTEXT_MAP = {
    'radio_reads': _UNIVERSAL_CONTEXT_FILES | {
        'radio-chart-show-convention.md',
        'chart-show-glossary.md',
        'radio-read-examples.md',
    },
    'infographic': _UNIVERSAL_CONTEXT_FILES | {
        'infographic-editorial-framework.md',
        'chart-show-glossary.md',
    },
    'social': _UNIVERSAL_CONTEXT_FILES | {
        'social-media-music-communities.md',
        'social-style-examples.md',
        'chart-show-glossary.md',
    },
}

# Per-section output token budgets. These override the default max_tokens
# when generating each section to prevent truncation.
SECTION_MAX_TOKENS = {
    'radio_reads': 4096,       # 10 position reads + structural sections
    'infographic': 3000,       # structured JSON with 10 track cards
    'social': 3000,            # multi-platform posts with hashtags
}


def select_context_for_section(personal_context, section_name):
    """Filter loaded context files to only those relevant to the given section."""
    relevant_files = SECTION_CONTEXT_MAP.get(section_name)
    if not relevant_files:
        # Unknown section — include everything (safe fallback)
        return personal_context
    return [
        item for item in personal_context
        if any(item['path'].endswith(f) for f in relevant_files)
    ]


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
    'headline': 'string (one-line week summary, reusable in socials)',
    'chart_story': 'string (2-3 sentence narrative of the week)',
    'movement_summary': 'string (one-line movement overview)',
    'chart_talk': [
        {
            'icon': 'Font Awesome class name (e.g. fa-trophy, fa-rocket, fa-star)',
            'headline': 'string (5-15 words, ALL CAPS, max 25 characters)',
            'body': 'string (1-2 sentences, max 90 characters)'
        }
    ],
    'track_cards': [
        {
            'rank': 'number',
            'display_text': 'Artist - Title',
            'movement_badge': 'string',
            'supporting_line': 'string (editorial note about this track)'
        }
    ],
    'self_review': {
        'facts_verified': True,
        'chart_talk_count': 6,
        'all_headlines_under_25_chars': True,
        'all_bodies_under_90_chars': True,
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
        return self.complete_text_with_bedrock_runtime(prompt, images=images)

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

    def complete_text_with_bedrock_runtime(self, prompt, images=None):
        if self.client is None:
            import boto3
            from botocore.config import Config
            self.client = boto3.client(
                'bedrock-runtime',
                config=Config(connect_timeout=10, read_timeout=int(self.read_timeout), retries={'max_attempts': 0})
            )

        # Build content array with text and optional images
        content = [{'type': 'text', 'text': prompt}]
        if images:
            for image in images:
                if not isinstance(image, dict):
                    continue
                image_url = image.get('image_url') or image.get('data_uri') or ''
                if not image_url:
                    continue
                # Extract base64 data and media type from data URI
                if image_url.startswith('data:'):
                    parts = image_url.split(',', 1)
                    if len(parts) == 2:
                        header = parts[0]  # e.g., data:image/png;base64
                        media_type = header.replace('data:', '').split(';')[0]
                        data = parts[1]
                        content.insert(0, {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': data
                            }
                        })

        body = {
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'messages': [
                {
                    'role': 'user',
                    'content': content
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
    section_context = select_context_for_section(personal_context, section_name)
    prompt_package = build_generation_prompt_package(
        section_name,
        chart_brief,
        venue_config,
        agent_spec,
        section_context,
        memory_context,
        schema,
        prompt_config=prompt_config
    )
    if prompt_refs is not None:
        prompt_refs[section_name] = prompt_package['ref']

    # Override token budget for this section if configured
    section_tokens = SECTION_MAX_TOKENS.get(section_name)
    original_max_tokens = model_client.max_tokens
    if section_tokens:
        model_client.max_tokens = section_tokens

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
    finally:
        model_client.max_tokens = original_max_tokens


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
