#!/usr/bin/env python3
"""Small unit tests for AgentCore tool name handling."""
import os
import sys
import types
from types import SimpleNamespace

os.environ.setdefault('CHART_HISTORY_TABLE', 'chart-history-test')
os.environ.setdefault('CAMPAIGNS_TABLE', 'campaigns-test')
os.environ.setdefault('CONFIG_TABLE', 'config-test')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../layers/common'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/agentcore-tools'))


class FakeDynamoDB:
    def Table(self, name):
        return name


class FakeBoto3:
    def resource(self, name):
        assert name == 'dynamodb'
        return FakeDynamoDB()

    def client(self, name):
        return SimpleNamespace()


conditions_module = types.ModuleType('boto3.dynamodb.conditions')


class FakeCondition:
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


conditions_module.Key = FakeCondition
conditions_module.Attr = FakeCondition
dynamodb_module = types.ModuleType('boto3.dynamodb')
dynamodb_module.conditions = conditions_module
boto3_module = types.ModuleType('boto3')
boto3_module.resource = FakeBoto3().resource
boto3_module.client = FakeBoto3().client

sys.modules['boto3'] = boto3_module
sys.modules['boto3.dynamodb'] = dynamodb_module
sys.modules['boto3.dynamodb.conditions'] = conditions_module

import app


context = SimpleNamespace(
    client_context=SimpleNamespace(
        custom={'bedrockAgentCoreToolName': 'ChartCampaignTools___create_chart_brief'}
    )
)

assert app.strip_gateway_prefix('ChartCampaignTools___get_current_chart') == 'get_current_chart'
assert app.resolve_tool_name({}, context) == 'create_chart_brief'
assert app.resolve_tool_name({'tool': 'get_chart_week'}, None) == 'get_chart_week'
assert app.parse_sections(None) == ['radio', 'infographic', 'social']
assert app.parse_sections('radio') == ['radio']
assert app.extract_response_image_base64(
    SimpleNamespace(output=[SimpleNamespace(type='image_generation_call', result='aW1hZ2U=')])
) == 'aW1hZ2U='
assert app.extract_response_image_base64({
    'output': [{
        'content': [{
            'type': 'output_image',
            'image': {'b64_json': 'cG5n'}
        }]
    }]
}) == 'cG5n'

image_prompt = app.build_infographic_image_prompt({
    'week_id': '2026-07-25',
    'chart_brief': {'tracks': [{'rank': 1, 'track': 'Artist - Song'}]},
    'infographic': {'headline': 'Headline'},
    'infographic_asset': {
        'metadata': {
            'brand_config_snapshot': {
                'chart_title': "Muddy's Top 10",
                'tagline': 'Your requests. Your music. Your chart.'
            }
        }
    }
})
assert 'attached PNG' in image_prompt
assert 'CHART BRIEF JSON' in image_prompt
assert "Muddy's Top 10" in image_prompt

print('AgentCore tool tests passed')
