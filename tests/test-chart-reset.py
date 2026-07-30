#!/usr/bin/env python3
"""Test chart reset time calculation in PST"""

import sys
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Add layers/common to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../layers/common'))

from common import get_chart_week_start

# Test cases
test_cases = [
    {
        'name': 'Saturday 4am PST - Before reset (Friday)',
        'current_time': datetime(2026, 3, 27, 10, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles')),  # Friday 10am PST
        'day': 'saturday',
        'hour': 4,
        'expected': datetime(2026, 3, 21, 4, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles'))  # Last Saturday 4am PST
    },
    {
        'name': 'Saturday 4am PST - After reset (Saturday noon)',
        'current_time': datetime(2026, 3, 28, 12, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles')),  # Saturday 12pm PST
        'day': 'saturday',
        'hour': 4,
        'expected': datetime(2026, 3, 28, 4, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles'))  # This Saturday 4am PST
    },
    {
        'name': 'Saturday 4am PST - Just before reset (3:59am)',
        'current_time': datetime(2026, 3, 28, 3, 59, 0, tzinfo=ZoneInfo('America/Los_Angeles')),  # Saturday 3:59am PST
        'day': 'saturday',
        'hour': 4,
        'expected': datetime(2026, 3, 21, 4, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles'))  # Last Saturday 4am PST
    },
    {
        'name': 'Monday midnight PST (default)',
        'current_time': datetime(2026, 3, 27, 10, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles')),  # Friday 10am PST
        'day': 'monday',
        'hour': 0,
        'expected': datetime(2026, 3, 23, 0, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles'))  # This Monday midnight PST
    }
]

print("╔════════════════════════════════════════════════════════════════╗")
print("║         Testing Chart Reset Time (PST)                        ║")
print("╚════════════════════════════════════════════════════════════════╝")
print()

passed = 0
failed = 0

for test in test_cases:
    print(f"Test: {test['name']}")
    print(f"  Current time: {test['current_time'].strftime('%A %Y-%m-%d %I:%M %p %Z')}")
    print(f"  Config: {test['day'].title()} at {test['hour']}:00")

    # Convert to timestamp for function
    current_ts = int(test['current_time'].timestamp())

    # Get chart week start
    result_ts = get_chart_week_start(current_ts, test['day'], test['hour'])
    result_dt = datetime.fromtimestamp(result_ts, tz=ZoneInfo('America/Los_Angeles'))

    expected_ts = int(test['expected'].timestamp())

    print(f"  Expected: {test['expected'].strftime('%A %Y-%m-%d %I:%M %p %Z')}")
    print(f"  Got:      {result_dt.strftime('%A %Y-%m-%d %I:%M %p %Z')}")

    if result_ts == expected_ts:
        print("  ✅ PASS")
        passed += 1
    else:
        print("  ❌ FAIL")
        print(f"     Expected timestamp: {expected_ts}")
        print(f"     Got timestamp:      {result_ts}")
        print(f"     Difference: {(result_ts - expected_ts) / 3600} hours")
        failed += 1
    print()

print("═" * 64)
print(f"Results: {passed} passed, {failed} failed")
print("═" * 64)

sys.exit(0 if failed == 0 else 1)
