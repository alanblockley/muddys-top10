#!/usr/bin/env python3
"""Tests for the Strands-backed AgentCore Runtime action router."""
import importlib
import os
import sys
import types
from types import SimpleNamespace


os.environ.setdefault('AGENTCORE_TOOLS_FUNCTION_NAME', 'agentcore-tools-test')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/agentcore-runtime'))


class FakeBedrockAgentCoreApp:
    def entrypoint(self, fn):
        return fn

    def run(self):
        pass


def fake_tool(fn):
    return fn


class FakeToolNamespace:
    def __init__(self, tools):
        for item in tools:
            setattr(self, item.__name__, item)


class FakeAgent:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.tool = FakeToolNamespace(kwargs.get('tools') or [])


bedrock_agentcore_module = types.ModuleType('bedrock_agentcore')
bedrock_agentcore_module.BedrockAgentCoreApp = FakeBedrockAgentCoreApp
strands_module = types.ModuleType('strands')
strands_module.Agent = FakeAgent
strands_module.tool = fake_tool

sys.modules['bedrock_agentcore'] = bedrock_agentcore_module
sys.modules['strands'] = strands_module

runtime = importlib.import_module('main')


class FakePayload:
    def __init__(self, value):
        self.value = value

    def read(self):
        return self.value.encode('utf-8')


class FakeLambdaClient:
    def __init__(self):
        self.payloads = []

    def invoke(self, **kwargs):
        import json
        payload = json.loads(kwargs['Payload'].decode('utf-8'))
        self.payloads.append(payload)
        return {
            'Payload': FakePayload(json.dumps({
                'ok': True,
                'tool': payload['tool'],
                'echo': payload
            }))
        }


fake_lambda = FakeLambdaClient()
runtime._lambda_client = fake_lambda

created = runtime.invoke({
    'action': 'create_chart_campaign',
    'week_id': '2026-07-20',
    'sections': ['infographic'],
    'requested_by': 'tester'
})
assert created['ok'] is True
assert created['tool'] == 'create_chart_campaign'
assert fake_lambda.payloads[-1]['generated_by'] == 'agentcore-runtime'

listed = runtime.invoke({
    'action': 'list_chart_campaigns',
    'limit': 5
})
assert listed['tool'] == 'list_chart_campaigns'
assert fake_lambda.payloads[-1]['limit'] == 5

got = runtime.invoke({
    'action': 'get_chart_campaign',
    'week_id': '2026-07-20'
})
assert got['tool'] == 'get_chart_campaign'

print('AgentCore runtime tests passed')
