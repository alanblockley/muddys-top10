#!/usr/bin/env python3
"""Test backup status parsing from XML format"""

import sys
import os
import xml.etree.ElementTree as ET
import html

# Add src/poller to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/poller'))

def parse_xml_format(data):
    """Parse stats?sid= XML format"""
    try:
        # Parse XML
        root = ET.fromstring(data)

        # Get SONGTITLE element
        songtitle = root.find('SONGTITLE')
        if songtitle is None or not songtitle.text:
            return None

        track = html.unescape(songtitle.text.strip())

        # Get BACKUPSTATUS element (0 or 1)
        backup_status = False
        backup_element = root.find('BACKUPSTATUS')
        if backup_element is not None and backup_element.text:
            backup_status = backup_element.text.strip() == '1'

        return {
            'track': track,
            'backup_status': backup_status
        }

    except Exception as e:
        print(f"Error parsing XML: {e}")
        return None


# Test cases
test_cases = [
    {
        'name': 'Normal stream (backup=0)',
        'xml': '''<?xml version="1.0" encoding="UTF-8"?>
<SHOUTCASTSERVER>
    <SONGTITLE>Artist Name - Track Title</SONGTITLE>
    <BACKUPSTATUS>0</BACKUPSTATUS>
</SHOUTCASTSERVER>''',
        'expected': {
            'track': 'Artist Name - Track Title',
            'backup_status': False
        }
    },
    {
        'name': 'Backup stream (backup=1)',
        'xml': '''<?xml version="1.0" encoding="UTF-8"?>
<SHOUTCASTSERVER>
    <SONGTITLE>HUNTR/X - What It Sounds Like</SONGTITLE>
    <BACKUPSTATUS>1</BACKUPSTATUS>
</SHOUTCASTSERVER>''',
        'expected': {
            'track': 'HUNTR/X - What It Sounds Like',
            'backup_status': True
        }
    },
    {
        'name': 'Missing BACKUPSTATUS',
        'xml': '''<?xml version="1.0" encoding="UTF-8"?>
<SHOUTCASTSERVER>
    <SONGTITLE>Artist - Song</SONGTITLE>
</SHOUTCASTSERVER>''',
        'expected': {
            'track': 'Artist - Song',
            'backup_status': False
        }
    },
    {
        'name': 'HTML entities in track name',
        'xml': '''<?xml version="1.0" encoding="UTF-8"?>
<SHOUTCASTSERVER>
    <SONGTITLE>Artist &amp; Co - Track &quot;Name&quot;</SONGTITLE>
    <BACKUPSTATUS>1</BACKUPSTATUS>
</SHOUTCASTSERVER>''',
        'expected': {
            'track': 'Artist & Co - Track "Name"',
            'backup_status': True
        }
    }
]

print("╔════════════════════════════════════════════════════════════════╗")
print("║           Testing Backup Status Parsing                       ║")
print("╚════════════════════════════════════════════════════════════════╝")
print()

passed = 0
failed = 0

for test in test_cases:
    print(f"Test: {test['name']}")
    result = parse_xml_format(test['xml'])

    if result == test['expected']:
        print("  ✅ PASS")
        print(f"     Track: {result['track']}")
        print(f"     Backup: {result['backup_status']}")
        passed += 1
    else:
        print("  ❌ FAIL")
        print(f"     Expected: {test['expected']}")
        print(f"     Got: {result}")
        failed += 1
    print()

print("═" * 64)
print(f"Results: {passed} passed, {failed} failed")
print("═" * 64)

sys.exit(0 if failed == 0 else 1)
