#!/usr/bin/env python3
"""Tests for AgentCore Memory filtering."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../layers/common'))

import agent_memory


class FakeClient:
    def retrieve_memory_records(self, **kwargs):
        return {
            'memoryRecordSummaries': [
                {
                    'memoryRecordId': 'past',
                    'content': 'Past campaign',
                    'metadata': {
                        'week_id': {
                            'stringValue': '2026-05-02'
                        }
                    }
                },
                {
                    'memoryRecordId': 'same',
                    'content': 'Same week campaign',
                    'metadata': {
                        'week_id': {
                            'stringValue': '2026-05-09'
                        }
                    }
                },
                {
                    'memoryRecordId': 'future',
                    'content': 'Future campaign',
                    'metadata': {
                        'week_id': {
                            'stringValue': '2026-05-16'
                        }
                    }
                },
                {
                    'memoryRecordId': 'unknown',
                    'content': 'Unknown week campaign',
                    'metadata': {}
                }
            ]
        }


original_client = agent_memory._client
original_memory_id = os.environ.get('AGENTCORE_MEMORY_ID')
agent_memory._client = lambda: FakeClient()
os.environ['AGENTCORE_MEMORY_ID'] = 'memory-id'
try:
    records = agent_memory.retrieve_campaign_memory({'week_id': '2026-05-09'})
finally:
    agent_memory._client = original_client
    if original_memory_id is None:
        os.environ.pop('AGENTCORE_MEMORY_ID', None)
    else:
        os.environ['AGENTCORE_MEMORY_ID'] = original_memory_id

assert [record['memory_record_id'] for record in records] == ['past']

print('Agent memory tests passed')
