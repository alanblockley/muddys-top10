#!/usr/bin/env python3
"""
Test both Shoutcast metadata parsers
"""

import html


def parse_7html_format(data):
    """Parse 7.html CSV format"""
    # Remove HTML tags
    data = data.replace('<html><body>', '').replace('</body></html>', '')
    parts = data.split(',')

    if len(parts) >= 7:
        track = ','.join(parts[6:])  # Handle tracks with commas
        return html.unescape(track.strip())
    return None


def parse_xml_format(data):
    """Parse stats?sid= XML format"""
    import xml.etree.ElementTree as ET

    try:
        # Parse XML
        root = ET.fromstring(data)

        # Get SONGTITLE element
        songtitle = root.find('SONGTITLE')
        if songtitle is not None and songtitle.text:
            return html.unescape(songtitle.text.strip())

        return None
    except Exception as e:
        print(f"Error parsing XML: {e}")
        return None


# Test 7.html format
print("Testing 7.html format:")
html_data = """<html><body>56,1,62,500,46,128,Artist - Song Title</body></html>"""
result = parse_7html_format(html_data)
print(f"  Input: {html_data}")
print(f"  Result: {result}")
print()

# Test XML format
print("Testing XML format:")
xml_data = """<?xml version="1.0" encoding="UTF-8"?>
<SHOUTCASTSERVER>
<CURRENTLISTENERS>82</CURRENTLISTENERS>
<PEAKLISTENERS>225</PEAKLISTENERS>
<MAXLISTENERS>500</MAXLISTENERS>
<UNIQUELISTENERS>79</UNIQUELISTENERS>
<AVERAGETIME>2275</AVERAGETIME>
<SERVERGENRE>Unspecified</SERVERGENRE>
<SERVERGENRE2/>
<SERVERGENRE3/>
<SERVERGENRE4/>
<SERVERGENRE5/>
<SERVERURL>http://localhost/</SERVERURL>
<SERVERTITLE>Muddy's Music Cafe AutoDJ</SERVERTITLE>
<SONGTITLE>Live @ Muddy's Music Cafe - DJ Twstd</SONGTITLE>
<STREAMHITS>256159</STREAMHITS>
<STREAMSTATUS>1</STREAMSTATUS>
<BACKUPSTATUS>0</BACKUPSTATUS>
<STREAMLISTED>0</STREAMLISTED>
<STREAMLISTEDERROR>0</STREAMLISTEDERROR>
<STREAMPATH>/stream</STREAMPATH>
<STREAMUPTIME>1683582</STREAMUPTIME>
<BITRATE>128</BITRATE>
<SAMPLERATE>44100</SAMPLERATE>
<CONTENT>audio/mpeg</CONTENT>
<VERSION>2.6.1.777 (posix(linux x64))</VERSION>
</SHOUTCASTSERVER>"""
result = parse_xml_format(xml_data)
print(f"  Result: {result}")
print()

# Test XML without XML declaration
print("Testing XML without declaration:")
xml_data_no_decl = """<SHOUTCASTSERVER>
<SONGTITLE>HUNTR/X - What It Sounds Like</SONGTITLE>
</SHOUTCASTSERVER>"""
result = parse_xml_format(xml_data_no_decl)
print(f"  Result: {result}")
print()

# Test with HTML entities
print("Testing HTML entities:")
xml_data_entities = """<SHOUTCASTSERVER>
<SONGTITLE>Artist &amp; Friends - Song &quot;Title&quot;</SONGTITLE>
</SHOUTCASTSERVER>"""
result = parse_xml_format(xml_data_entities)
print(f"  Result: {result}")
