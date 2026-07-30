#!/usr/bin/env python3
"""Tests for deterministic agentic campaign services."""
import os
import sys
import types
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../layers/common'))

conditions_module = types.ModuleType('boto3.dynamodb.conditions')


class FakeKey:
    def __init__(self, name):
        self.name = name

    def eq(self, value):
        return self

    def begins_with(self, value):
        return self

    def lt(self, value):
        return self

    def __and__(self, other):
        return self


conditions_module.Key = FakeKey
dynamodb_module = types.ModuleType('boto3.dynamodb')
dynamodb_module.conditions = conditions_module
boto3_module = types.ModuleType('boto3')
sys.modules.setdefault('boto3', boto3_module)
sys.modules.setdefault('boto3.dynamodb', dynamodb_module)
sys.modules.setdefault('boto3.dynamodb.conditions', conditions_module)

import campaign_generation
from chart_brief import build_chart_brief
from campaign_store import (
    approve_campaign_revision,
    campaign_revision_index_item,
    create_campaign_revision,
    delete_campaign_records,
    list_all_campaign_feedback,
    list_campaign_feedback,
    put_campaign_feedback,
    summarize_campaign_feedback
)
from campaign_generation import BedrockCampaignModel, create_campaign_draft, extract_infographic_asset_output, extract_json_object
from infographic_asset_validator import validate_infographic_asset
from prompt_management import normalize_prompt_config, render_managed_prompt, render_prompt_template


def snapshot(week_id, tracks):
    return {
        'pk': 'TOP10_HISTORY',
        'sk': f'WEEK#{week_id}',
        'week_id': week_id,
        'snapshot_type': 'weekly_top10',
        'week_start_timestamp': 1774072800,
        'week_end_timestamp': 1774677600,
        'chart_config': {'day': 'saturday', 'hour': 4},
        'filter_patterns': ['banned song'],
        'top10': tracks,
        'summary': {
            'total_plays': sum(track['play_count'] for track in tracks),
            'unique_tracks': len(tracks)
        },
        'chart_date': f'{week_id}T04:00:00-07:00',
        'week_start': f'{week_id}T04:00:00-07:00',
        'week_end': f'{week_id}T04:00:00-07:00'
    }


previous = snapshot('2026-07-13', [
    {'rank': 1, 'track': 'Artist A - Song A', 'play_count': 10, 'previous_rank': None, 'movement': 'new', 'movement_delta': None},
    {'rank': 2, 'track': 'Artist B - Song B', 'play_count': 8, 'previous_rank': None, 'movement': 'new', 'movement_delta': None},
    {'rank': 3, 'track': 'Artist C - Song C', 'play_count': 7, 'previous_rank': None, 'movement': 'new', 'movement_delta': None}
])

current = snapshot('2026-07-20', [
    {'rank': 1, 'track': 'Artist B - Song B', 'play_count': 12, 'previous_rank': 2, 'movement': 'up', 'movement_delta': 1},
    {'rank': 2, 'track': 'Artist D - Song D', 'play_count': 9, 'previous_rank': None, 'movement': 'new', 'movement_delta': None},
    {'rank': 3, 'track': 'Artist A - Song A', 'play_count': 8, 'previous_rank': 1, 'movement': 'down', 'movement_delta': -2}
])

future = snapshot('2026-07-27', [
    {'rank': 1, 'track': 'Artist D - Song D', 'play_count': 99, 'previous_rank': 2, 'movement': 'up', 'movement_delta': 1},
    {'rank': 2, 'track': 'Artist Z - Song Z', 'play_count': 88, 'previous_rank': None, 'movement': 'new', 'movement_delta': None}
])

brief = build_chart_brief(current, [previous, future])

assert brief['week_id'] == '2026-07-20'
assert brief['source_snapshot_key'] == 'WEEK#2026-07-20'
assert brief['summary']['history_weeks_available'] == 1
assert brief['tracks'][0]['artist'] == 'Artist B'
assert brief['tracks'][0]['title'] == 'Song B'
assert brief['tracks'][0]['weeks_on_chart'] == 2
assert brief['tracks'][0]['best_rank'] == 1
assert brief['tracks'][0]['last_seen_week'] == '2026-07-13'
assert brief['tracks'][1]['movement'] == 'new'
assert brief['tracks'][1]['weeks_on_chart'] == 1
assert brief['tracks'][1]['best_rank'] == 2
assert brief['tracks'][1]['last_seen_week'] is None
assert brief['notables']['number_one']['track'] == 'Artist B - Song B'
assert brief['notables']['biggest_climbers'][0]['track'] == 'Artist B - Song B'
assert brief['notables']['biggest_drops'][0]['track'] == 'Artist A - Song A'

campaign = create_campaign_draft(brief, generated_by='test')
uploaded_branding = campaign_generation.normalize_campaign_branding({
    'logo_s3_key': 'branding/logo-test.png',
    'logo_content_type': 'image/png',
    'logo_filename': 'logo-test.png',
    'chart_title': 'Saturday Night Top 10',
    'tagline': 'Built by the dance floor.',
    'color_scheme': 'custom',
    'primary_color': '#123abc',
    'secondary_color': '456def',
    'accent_color': '#abcdef',
    'background_color': '#000111',
    'text_color': '#fffeee',
    'font_family': 'georgia'
})
assert uploaded_branding['logo_s3_key'] == 'branding/logo-test.png'
assert uploaded_branding['logo_content_type'] == 'image/png'
assert uploaded_branding['logo_filename'] == 'logo-test.png'
assert uploaded_branding['chart_title_text'] == 'Saturday Night Top 10'
assert uploaded_branding['tagline_text'] == 'Built by the dance floor.'
assert uploaded_branding['color_scheme'] == 'custom'
assert uploaded_branding['primary_color'] == '#123abc'
assert uploaded_branding['secondary_color'] == '#456def'
assert uploaded_branding['font_family'] == 'georgia'
assert uploaded_branding['font_family_css'] == 'Georgia, serif'
legacy_branding = campaign_generation.normalize_campaign_branding({
    'chart_title': 'muddys_weekly_chart',
    'tagline': 'community_countdown'
})
assert legacy_branding['chart_title_text'] == "Muddy's Weekly Chart"
assert legacy_branding['tagline_text'] == 'The countdown powered by our community.'

assert campaign['pk'] == 'CAMPAIGN'
assert campaign['sk'] == 'WEEK#2026-07-20'
assert campaign['status'] == 'draft'
assert campaign['generated_by'] == 'test'
assert campaign['radio_reads']['position_reads'][0]['rank'] == 1
assert campaign['infographic']['track_cards'][0]['display_text'] == 'Artist B - Song B'
assert campaign['infographic_asset']['metadata']['template_id'] == 'classic_chart_poster'
assert campaign['infographic_asset']['metadata']['template_version'] == '1'
assert '{{MUDDYS_LOGO_DATA_URI}}' in campaign['infographic_asset']['html']
assert campaign['infographic_asset_validation']['valid'] is True
bad_asset = dict(campaign['infographic_asset'])
bad_asset['html'] = '<script>alert(1)</script>'
assert validate_infographic_asset(bad_asset, brief)['valid'] is False
assert 'facebook' in campaign['social']
assert campaign['generator']['prompt_version'] == 'agentic-campaign-v1'
revision = create_campaign_revision(campaign, parent_revision_id='previous-revision')
assert revision['pk'] == 'CAMPAIGN_REVISION'
assert revision['week_id'] == '2026-07-20'
assert revision['parent_revision_id'] == 'previous-revision'
assert revision['infographic_asset']['metadata']['template_id'] == 'classic_chart_poster'
revision_index = campaign_revision_index_item(revision)
assert revision_index['template_id'] == 'classic_chart_poster'
assert revision_index['href'].endswith(f"/revisions/{revision['revision_id']}")


class FakeCampaignTable:
    def __init__(self, items):
        self.items = items

    def get_item(self, Key):
        item = self.items.get((Key['pk'], Key['sk']))
        return {'Item': item} if item else {}

    def put_item(self, Item):
        self.items[(Item['pk'], Item['sk'])] = Item

    def update_item(self, Key, UpdateExpression=None, ExpressionAttributeNames=None, ExpressionAttributeValues=None, **kwargs):
        item = self.items[(Key['pk'], Key['sk'])]
        item['status'] = ExpressionAttributeValues[':status']
        item['approved_by'] = ExpressionAttributeValues[':approved_by']
        item['approved_at'] = ExpressionAttributeValues[':approved_at']
        return {'Attributes': item}


fake_table = FakeCampaignTable({
    ('CAMPAIGN_REVISION', revision['sk']): revision,
    ('CAMPAIGN', campaign['sk']): campaign
})
approved_campaign = approve_campaign_revision(
    fake_table,
    '2026-07-20',
    revision['revision_id'],
    actor='tester',
    timestamp='2026-07-28T00:00:00+00:00'
)
assert approved_campaign['status'] == 'approved'
assert approved_campaign['approved_revision_id'] == revision['revision_id']
assert approved_campaign['active_revision_id'] == revision['revision_id']
assert fake_table.items[('CAMPAIGN_REVISION', revision['sk'])]['status'] == 'approved'


class FakeFeedbackTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item['pk'], Item['sk'])] = Item

    def delete_item(self, Key, ReturnValues=None):
        item = self.items.pop((Key['pk'], Key['sk']), None)
        return {'Attributes': item} if item and ReturnValues == 'ALL_OLD' else {}

    def query(self, KeyConditionExpression=None, ScanIndexForward=None, Limit=None, IndexName=None, **kwargs):
        if IndexName == 'gsi1':
            items = [
                item for item in self.items.values()
                if item.get('gsi_pk') == 'FEEDBACK_SUMMARY'
            ]
            return {'Items': items[:Limit or len(items)]}

        prefix = f"WEEK#{revision['week_id']}#REV#{revision['revision_id']}#"
        items = [
            item for (pk, sk), item in self.items.items()
            if pk == 'CAMPAIGN_FEEDBACK' and sk.startswith(prefix)
        ]
        return {'Items': items[:Limit or len(items)]}


feedback_table = FakeFeedbackTable()
feedback = put_campaign_feedback(feedback_table, {
    'week_id': revision['week_id'],
    'revision_id': revision['revision_id'],
    'asset_type': 'infographic',
    'rating': 'down',
    'feedback_text': 'Layout felt too static.',
    'prompt_refs': {'infographic_asset': {'source': 'code'}},
    'model_id': 'fake-model',
    'created_at': '2026-07-28T00:00:00+00:00',
    'created_by': 'tester'
})
assert feedback['pk'] == 'CAMPAIGN_FEEDBACK'
assert feedback['asset_type'] == 'infographic'
assert feedback['rating'] == 'down'
assert feedback['prompt_refs']['infographic_asset']['source'] == 'code'
assert list_campaign_feedback(feedback_table, revision['week_id'], revision['revision_id'])[0]['feedback_text'] == 'Layout felt too static.'
put_campaign_feedback(feedback_table, {
    'week_id': revision['week_id'],
    'revision_id': revision['revision_id'],
    'asset_type': 'social',
    'rating': 'up',
    'prompt_refs': {'social': {'source': 'bedrock_prompt_management', 'prompt_identifier': 'social-prompt', 'prompt_version': '1'}},
    'model_id': 'fake-model',
    'created_at': '2026-07-28T00:01:00+00:00',
    'created_by': 'tester'
})
feedback_items = list_all_campaign_feedback(feedback_table, 10)
feedback_summary = summarize_campaign_feedback(feedback_items)
assert feedback_summary['total'] == 2
assert feedback_summary['ratings']['down'] == 1
assert feedback_summary['asset_types'][0]['count'] == 1
assert feedback_summary['models'][0]['key'] == 'fake-model'
assert feedback_summary['recent_negative'][0]['feedback_text'] == 'Layout felt too static.'
cleanup_table = FakeFeedbackTable()
cleanup_campaign = dict(campaign)
cleanup_campaign['infographic_png'] = {'bucket': 'assets', 'key': 'campaigns/2026-07-20/one.png'}
cleanup_table.put_item(cleanup_campaign)
cleanup_revision = create_campaign_revision(cleanup_campaign)
cleanup_table.put_item(cleanup_revision)
cleanup_table.put_item(feedback)
deleted_records = delete_campaign_records(cleanup_table, '2026-07-20')
assert deleted_records['campaign']['week_id'] == '2026-07-20'
assert deleted_records['deleted_revision_count'] == 1
assert deleted_records['deleted_feedback_count'] == 1
assert BedrockCampaignModel('anthropic.claude-sonnet-5').endpoint == 'bedrock-mantle'
assert extract_json_object('```json\n{"ok": true}\n```')['ok'] is True
asset_blocks = extract_infographic_asset_output(
    '```html\n<section class="poster"><h1>Muddy</h1></section>\n```\n'
    '```css\n.poster{width:1280px;height:720px}\n```'
)
assert asset_blocks['html'].startswith('<section')
assert asset_blocks['css'].startswith('.poster')
labelled_asset = extract_infographic_asset_output(
    'HTML:\n<section class="poster"><h1>Muddy</h1></section>\n\n'
    'CSS:\n.poster{width:1280px;height:720px}'
)
assert labelled_asset['metadata']['output_format'] == 'html_css_blocks'
legacy_asset = extract_infographic_asset_output(
    '{"html":"<section class=\\"poster\\"></section>","css":".poster{width:1280px;height:720px}"}'
)
assert legacy_asset['metadata']['output_format'] == 'legacy_json_html_css'

prompt_config = normalize_prompt_config({
    'radio_reads': {
        'prompt_identifier': 'prompt-abc',
        'prompt_version': 3
    },
    'unknown': {
        'prompt_identifier': 'ignored'
    }
})
assert prompt_config['radio_reads']['prompt_identifier'] == 'prompt-abc'
assert prompt_config['radio_reads']['prompt_version'] == '3'
assert prompt_config['social']['prompt_identifier'] == ''
assert render_prompt_template('Hello {{ name }}', {'name': 'Muddy'}) == 'Hello Muddy'


class FakePromptClient:
    def get_prompt(self, **kwargs):
        assert kwargs['promptIdentifier'] == 'prompt-abc'
        assert kwargs['promptVersion'] == '3'
        return {
            'arn': 'arn:aws:bedrock:us-west-2:123456789012:prompt/prompt-abc',
            'version': '3',
            'defaultVariant': 'default',
            'variants': [
                {
                    'name': 'default',
                    'templateConfiguration': {
                        'text': {
                            'text': 'SECTION={{section_name}}\nBRIEF={{chart_brief_json}}'
                        }
                    }
                }
            ]
        }


managed_prompt = render_managed_prompt(
    'radio_reads',
    prompt_config,
    {'section_name': 'radio_reads', 'chart_brief_json': '{"week_id":"2026-07-20"}'},
    bedrock_agent_client=FakePromptClient()
)
assert managed_prompt['ref']['source'] == 'bedrock_prompt_management'
assert managed_prompt['ref']['prompt_version'] == '3'
assert 'SECTION=radio_reads' in managed_prompt['text']


class FakeModel:
    model_id = 'fake-model'
    prompts = []

    def complete_text(self, prompt, response_format=None):
        self.prompts.append(prompt)
        if 'final Muddy' in prompt and 'fenced code blocks' in prompt:
            rows = ''.join(
                f'<li><b>{i}</b><span>Artist {chr(64+i) if i < 3 else i}</span><span>Song {chr(64+i) if i < 3 else i}</span><em>{i} plays</em></li>'
                for i in range(1, 11)
            )
            return (
                '```html\n'
                '<section class="poster"><img src="{{MUDDYS_LOGO_DATA_URI}}" alt="logo">'
                "<h1>Muddy&#39;s Top 10</h1><p>Your requests. Your music. Your chart.</p>"
                f'<ol>{rows}</ol></section>\n'
                '```\n'
                '```css\n'
                '.poster{width:1280px;height:720px;color:#f8fafc;background:#050005}.poster h1{color:#a855f7}\n'
                '```'
            )
        return json.dumps(self.complete_json(prompt))

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        if 'SECTION:\nradio_reads' in prompt:
            return {
                'intro': 'Model radio intro',
                'top10_intro': 'Model top ten intro',
                'top5_recap': 'Model top five',
                'top3_recap': 'Model top three',
                'outro': 'Model outro',
                'position_reads': [],
                'self_review': {'facts_verified': True, 'pg_broadcast_appropriate': True, 'missing_inputs': []}
            }
        if 'SECTION:\ninfographic' in prompt:
            return {
                'headline': 'Model headline',
                'subhead': 'Model subhead',
                'chart_story': 'Model story',
                'movement_summary': 'Model movement',
                'statistics': [],
                'track_cards': [],
                'promotional_footer': 'Model footer',
                'self_review': {'facts_verified': True, 'ready_for_publication': True, 'missing_inputs': []}
            }
        return {
            'facebook': {'post': "Model facebook post: #1 Artist B - Song B leads this week's Muddy's Top 10 with a full chart story, movement context, community tone, and enough detail for a complete social update.", 'hashtags': []},
            'primfeed': {'post': "Model primfeed post: #1 Artist B - Song B leads this week's Muddy's Top 10 with a full chart story and enough detail for a complete social update.", 'hashtags': []},
            'discord': {'post': "Model discord post: #1 Artist B - Song B leads this week's Muddy's Top 10 with chart movement and listener energy."},
            'teaser': {'short_copy': 'Model teaser for #1 Artist B - Song B'},
            'alt_text': 'Model alt text',
            'self_review': {'facts_verified': True, 'pg_appropriate': True, 'missing_inputs': []}
        }


original_from_env = BedrockCampaignModel.from_env
original_retrieve_memory = campaign_generation.retrieve_campaign_memory
original_remember_campaign = campaign_generation.remember_campaign
fake_model = FakeModel()
BedrockCampaignModel.from_env = classmethod(lambda cls: fake_model)
campaign_generation.retrieve_campaign_memory = lambda chart_brief: [
    {
        'memory_record_id': 'memory-1',
        'content': 'Last week used the phrase big mover; avoid repeating it.',
        'score': 0.91
    }
]
campaign_generation.remember_campaign = lambda campaign: 'event-1'
try:
    model_campaign = create_campaign_draft(brief, generated_by='test-model')
finally:
    BedrockCampaignModel.from_env = original_from_env
    campaign_generation.retrieve_campaign_memory = original_retrieve_memory
    campaign_generation.remember_campaign = original_remember_campaign

assert model_campaign['generator']['mode'] == 'bedrock-mantle-json-v1'
assert model_campaign['generator']['model_endpoint'] == 'bedrock-mantle'
assert model_campaign['generator']['model'] == 'fake-model'
assert model_campaign['generator']['memory_records_used'] == 1
assert model_campaign['generator']['memory_event_id'] == 'event-1'
assert model_campaign['generator']['prompt_refs']['radio_reads']['source'] == 'code'
assert model_campaign['generator']['prompt_refs']['infographic_asset']['source'] == 'code'
assert model_campaign['memory_refs'][0]['memory_record_id'] == 'memory-1'
assert model_campaign['radio_reads']['intro'] == 'Model radio intro'
assert model_campaign['radio_reads']['generation_mode'] == 'model_with_deterministic_position_reads'
assert model_campaign['infographic']['headline'] == 'Model headline'
assert model_campaign['infographic_asset']['metadata']['asset_generation_mode'] == 'model'
assert model_campaign['social']['facebook']['post'].startswith('Model facebook post')
assert any('AGENTCORE MEMORY CONTEXT' in prompt for prompt in fake_model.prompts)
assert any('avoid repeating' in prompt for prompt in fake_model.prompts)
assert any('STARTING TEMPLATE HTML' in prompt for prompt in fake_model.prompts)

print('Agentic campaign tests passed')
