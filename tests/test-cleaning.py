#!/usr/bin/env python3
"""
Test track title cleaning
"""
import sys
import os

# Add layers/common to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'layers/common'))

from common import clean_track_title

# Test cases
test_tracks = [
    "Sombr - 12 To 12",
    "Artist - Song 128",
    "Artist - Song 125",
    "Artist - Song 1",
    "Artist - Song 12",
    "Artist - Track 99",
    "Artist - Track 100",
    "Artist - Track 150",
    "Artist - Track 200",
    "Artist - Track 201",
    "Artist - 24 Hours",
    "Artist - 3AM",
]

print("Testing track cleaning:")
print()

for track in test_tracks:
    cleaned = clean_track_title(track)
    changed = " ✓" if cleaned != track else ""
    print(f"Input:   {track}")
    print(f"Output:  {cleaned}{changed}")
    print()
