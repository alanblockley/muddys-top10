"""Strands-backed AgentCore Runtime for Muddy's weekly chart campaigns.

The runtime keeps the public AgentCore action contract stable while moving the
internal orchestration onto Strands tools. Creative generation still happens in
the Lambda-backed tool service for now; this runtime owns routing and tool
execution.
"""
import json
import os

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool


app = BedrockAgentCoreApp()
_lambda_client = None
_campaign_agent = None


@app.entrypoint
def invoke(payload):
    payload = payload or {}
    action = payload.get('action') or 'create_chart_campaign'
    agent = campaign_agent()

    if action == 'create_chart_campaign':
        return normalize_tool_result(agent.tool.create_chart_campaign(
            week_id=payload.get('week_id'),
            sections=payload.get('sections'),
            requested_by=payload.get('requested_by'),
            generated_by=payload.get('generated_by') or 'agentcore-runtime'
        ))
    if action == 'get_chart_campaign':
        return normalize_tool_result(agent.tool.get_chart_campaign(
            week_id=payload.get('week_id')
        ))
    if action == 'list_chart_campaigns':
        return normalize_tool_result(agent.tool.list_chart_campaigns(
            limit=payload.get('limit'),
            next_token=payload.get('next_token')
        ))

    raise ValueError(f'Unknown runtime action: {action}')


@tool
def create_chart_campaign(week_id: str = None, sections: list = None, requested_by: str = None, generated_by: str = 'agentcore-runtime') -> dict:
    """Create or regenerate a weekly Muddy's Top 10 campaign."""
    return call_tool({
        'tool': 'create_chart_campaign',
        'week_id': week_id,
        'sections': sections,
        'requested_by': requested_by,
        'generated_by': generated_by or 'agentcore-runtime'
    })


@tool
def get_chart_campaign(week_id: str) -> dict:
    """Get one generated Muddy's Top 10 campaign by week id."""
    return call_tool({
        'tool': 'get_chart_campaign',
        'week_id': week_id
    })


@tool
def list_chart_campaigns(limit: int = None, next_token: str = None) -> dict:
    """List generated Muddy's Top 10 campaigns."""
    return call_tool({
        'tool': 'list_chart_campaigns',
        'limit': limit,
        'next_token': next_token
    })


def campaign_agent():
    global _campaign_agent
    if _campaign_agent is None:
        _campaign_agent = Agent(
            name='muddys_campaign_runtime',
            description='Routes Muddy Top 10 campaign actions to approved AgentCore tools.',
            system_prompt=(
                "You are the Muddy's Top 10 campaign runtime. "
                "Use only the provided tools. Chart facts come from tool responses. "
                "Do not invent rankings, movement, play counts, or campaign status."
            ),
            tools=[
                create_chart_campaign,
                get_chart_campaign,
                list_chart_campaigns
            ]
        )
    return _campaign_agent


def call_tool(tool_payload):
    function_name = os.environ.get('AGENTCORE_TOOLS_FUNCTION_NAME')
    if not function_name:
        raise RuntimeError('AGENTCORE_TOOLS_FUNCTION_NAME is not configured')

    response = lambda_client().invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(tool_payload).encode('utf-8')
    )
    raw_payload = response.get('Payload').read().decode('utf-8')
    result = json.loads(raw_payload or '{}')
    if response.get('FunctionError'):
        raise RuntimeError(result.get('errorMessage') or raw_payload or 'AgentCore tool invocation failed')
    if not result.get('ok', False):
        raise RuntimeError(result.get('error') or 'AgentCore tool failed')
    return result


def normalize_tool_result(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, 'content'):
        return value.content
    if hasattr(value, 'result'):
        return value.result
    return value


def lambda_client():
    global _lambda_client
    if _lambda_client is None:
        import boto3
        from botocore.config import Config
        _lambda_client = boto3.client(
            'lambda',
            config=Config(connect_timeout=10, read_timeout=300, retries={'max_attempts': 0})
        )
    return _lambda_client


if __name__ == '__main__':
    app.run()
