# Social Media Export Feature

The Top 10 page includes a **Download for Social Media** button that generates a shareable infographic of the current week's chart.

## How It Works

1. **Load the Top 10 page** - The chart data is fetched from the API
2. **Click "📥 Download for Social Media"** - Button appears once data is loaded
3. **Image is generated** - Canvas API creates a styled infographic
4. **Download starts** - PNG file is saved to your device

## Infographic Specifications

### Dimensions
- **Size**: 1080 x 1350 pixels
- **Format**: PNG image
- **Orientation**: Portrait
- **Optimized for**: Instagram posts, Facebook, Twitter

### Design Elements

**Background**:
- Purple gradient (brand colors: #6366f1 to #8b5cf6)
- Subtle grid pattern overlay
- Professional, eye-catching design

**Header**:
- Muddy's Music Cafe logo (180x180px)
- Title: "Muddy's Music Cafe"
- Subtitle: "TOP 10 THIS WEEK"
- Date range (e.g., "Mar 20 - Mar 27, 2026")

**Top 10 List**:
- Each track on semi-transparent background box
- Green rank badge (#1-#10)
- Track name (bold, truncated if too long)
- Play count (e.g., "45 plays")
- Movement indicator with color coding:
  - 🟢 **Green (up)**: Track moved up
  - 🔴 **Red (down)**: Track moved down
  - ⚪ **Gray (same)**: No change
  - 🟡 **Yellow (new)**: New entry (★ NEW)

**Footer**:
- "Based on DJ plays & listener requests"
- Emphasizes authenticity of the chart

## File Naming

Downloaded files are automatically named:
```
muddys-top10-2026-03-27.png
```

Format: `muddys-top10-YYYY-MM-DD.png` (current date)

## Usage Tips

### Best Practices
- Download weekly on chart day for consistent social media posting
- Post to Instagram, Facebook, Twitter/X
- Use in Stories with text overlay
- Share in community groups

### Social Media Captions (Examples)

**Instagram**:
```
🎵 This week's Top 10 at Muddy's Music Cafe!

Based on real DJ plays and your requests 🔥

Which track is your favorite? Drop a 🎧 in the comments!

#MuddysMusicCafe #Top10 #LiveMusic #DJLife #MusicChart
```

**Twitter/X**:
```
📊 This week's Top 10 at Muddy's!

Real DJ plays + listener requests = authentic chart 🎵

[Track] taking the #1 spot with X plays! 🔥

#MuddysTop10
```

**Facebook**:
```
🎶 Our Top 10 Tracks This Week!

These are the songs YOU requested and our DJs played the most.

Thank you for making Muddy's Music Cafe the best place to discover great music!

See you on the dance floor! 💃🕺
```

## Technical Details

### Canvas Rendering
- Uses HTML5 Canvas API for image generation
- Logo loaded asynchronously from `assets/muddys-logo.png`
- Text truncation ensures long track names fit
- Gradient and pattern effects for visual appeal

### Browser Compatibility
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

### Performance
- Generates in ~1-2 seconds
- No server-side processing required
- Works offline once page is loaded

## Customization

Want to modify the design? Edit `frontend/index.html`:

### Change Canvas Size
```javascript
canvas.width = 1080;  // Width in pixels
canvas.height = 1350; // Height for Instagram portrait
```

Common sizes:
- Instagram Post: 1080 x 1080 (square)
- Instagram Story: 1080 x 1920 (tall)
- Facebook Post: 1200 x 630 (wide)
- Twitter Post: 1200 x 675 (wide)

### Change Colors
```javascript
// Background gradient
gradient.addColorStop(0, '#6366f1'); // Top color
gradient.addColorStop(1, '#8b5cf6'); // Bottom color

// Movement colors
const movementColors = {
    'up': '#10b981',    // Green
    'down': '#ef4444',  // Red
    'same': '#6b7280',  // Gray
    'new': '#fbbf24'    // Yellow/Gold
};
```

### Change Fonts
```javascript
ctx.font = 'bold 60px Arial, sans-serif'; // Title
ctx.font = '32px Arial, sans-serif';      // Subtitle
ctx.font = 'bold 28px Arial, sans-serif'; // Track names
```

## Troubleshooting

**Button doesn't appear**:
- Check browser console for API errors
- Ensure chart data loaded successfully
- Verify API endpoint is configured

**Logo doesn't appear**:
- Verify `assets/muddys-logo.png` exists
- Check browser console for image load errors
- Ensure S3 bucket has logo uploaded

**Download fails**:
- Check browser allows downloads
- Verify sufficient disk space
- Try different browser

**Image looks blurry**:
- Canvas size might be too small
- Increase dimensions for higher quality
- PNG format preserves quality

## Future Enhancements

Potential improvements:
- Multiple size options (Instagram, Facebook, Twitter)
- Weekly comparison stats
- QR code linking to live Top 10
- Animated GIF export
- Video export with music preview
- Branded watermark option
- Custom color themes
