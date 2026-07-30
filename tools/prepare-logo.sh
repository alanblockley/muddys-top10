#!/bin/bash
# Prepare logo for Spotify playlist cover
# Converts PNG to JPEG and resizes to meet Spotify requirements (max 256KB)

set -e

LOGO_SRC="frontend/assets/muddys-logo.png"
LOGO_DEST="layers/common/logo.jpg"

echo "📸 Preparing logo for Spotify playlist cover..."

# Check if source exists
if [ ! -f "$LOGO_SRC" ]; then
    echo "❌ Logo not found: $LOGO_SRC"
    exit 1
fi

# Convert to JPEG and resize if needed
# Spotify requires: JPEG, max 256KB
if command -v convert &> /dev/null; then
    echo "Converting PNG to JPEG..."
    convert "$LOGO_SRC" -resize 640x640 -quality 85 "$LOGO_DEST"

    # Check size
    SIZE=$(stat -f%z "$LOGO_DEST" 2>/dev/null || stat -c%s "$LOGO_DEST")
    SIZE_KB=$((SIZE / 1024))

    echo "✓ Logo created: $LOGO_DEST ($SIZE_KB KB)"

    if [ $SIZE -gt 262144 ]; then
        echo "⚠️  Warning: Logo is ${SIZE_KB}KB (max 256KB)"
        echo "   Reducing quality..."
        convert "$LOGO_SRC" -resize 640x640 -quality 70 "$LOGO_DEST"
        SIZE=$(stat -f%z "$LOGO_DEST" 2>/dev/null || stat -c%s "$LOGO_DEST")
        SIZE_KB=$((SIZE / 1024))
        echo "✓ Reduced to $SIZE_KB KB"
    fi
else
    echo "⚠️  ImageMagick not found. Copying as-is (may not work if PNG)..."
    cp "$LOGO_SRC" "$LOGO_DEST"
fi

echo "✅ Logo ready for Lambda deployment"
