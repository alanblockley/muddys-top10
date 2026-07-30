#!/usr/bin/env python3
"""
Test script to verify the stream URL is accessible
"""
import sys
import urllib3
import html

urllib3.disable_warnings()

STREAM_URL = "http://muddys.digistream.info:20398/7.html"


def test_stream():
    """Test fetching from the stream"""
    print(f"Testing stream URL: {STREAM_URL}")
    print("-" * 60)

    http = urllib3.PoolManager()

    try:
        response = http.request('GET', STREAM_URL, timeout=5.0)

        if response.status != 200:
            print(f"❌ Error: HTTP {response.status}")
            return False

        data = response.data.decode('utf-8').strip()
        data = data.replace('<html><body>', '').replace('</body></html>', '')
        parts = data.split(',')

        if len(parts) >= 7:
            listeners = parts[0]
            track = html.unescape(','.join(parts[6:]))

            print(f"✅ Stream is accessible!")
            print(f"Current listeners: {listeners}")
            print(f"Now playing: {track}")
            print("-" * 60)
            print("✅ Ready to deploy!")
            return True
        else:
            print(f"❌ Unexpected response format: {data}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = test_stream()
    sys.exit(0 if success else 1)
