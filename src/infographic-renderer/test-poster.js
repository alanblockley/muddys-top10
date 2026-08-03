/**
 * Test the chart poster locally.
 * 
 * Usage:
 *   node test-poster.js
 * 
 * Outputs:
 *   test-poster.html — open in browser to preview the design
 *   test-poster.png  — rendered PNG (only works if Playwright/Chromium available)
 */
const { buildPosterHtml, renderToPng } = require('./chart-poster');
const { writeFileSync } = require('node:fs');

const SAMPLE_DATA = {
  chart_title: "Top 10",
  tagline: "Your requests. Your music. Your chart.",
  week_display: "25 July – 1 August 2026",
  week_id: "2026-07-25",
  headline: "New number one as Olivia Dean takes the crown",
  chart_story: "After three weeks climbing steadily, Olivia Dean finally reaches the summit with Man I Need. Bruno Mars drops two places after a dominant three-week run at the top.",
  tracks: [
    { rank: 1, artist: "Olivia Dean", title: "Man I Need", plays: 33, movement: "up", delta: 3 },
    { rank: 2, artist: "Alex Warren", title: "FEVER DREAM", plays: 30, movement: "up", delta: 1 },
    { rank: 3, artist: "Bruno Mars", title: "I Just Might", plays: 29, movement: "down", delta: -2 },
    { rank: 4, artist: "BTS", title: "SWIM", plays: 29, movement: "down", delta: -2 },
    { rank: 5, artist: "Harry Styles", title: "Ready, Steady, Go!", plays: 23, movement: "up", delta: 2 },
    { rank: 6, artist: "The Weeknd", title: "Open Hearts", plays: 20, movement: "new", delta: null },
    { rank: 7, artist: "Dua Lipa", title: "Illusion", plays: 18, movement: "down", delta: -3 },
    { rank: 8, artist: "Sabrina Carpenter", title: "Taste", plays: 16, movement: "up", delta: 4 },
    { rank: 9, artist: "Billie Eilish", title: "Birds of a Feather", plays: 14, movement: "same", delta: 0 },
    { rank: 10, artist: "Taylor Swift", title: "Fortnight", plays: 12, movement: "reentry", delta: null },
  ],
  stats: { new_entries: 1, climbers: 5, fallers: 3, non_movers: 1 },
  show: { time: "2AM SLT", day: "EVERY SATURDAY", presenters: "DJ TOOHEY & JP" }
};

async function main() {
  console.log('=== Chart Poster Test ===\n');

  // Always output HTML (works without Playwright)
  const html = buildPosterHtml(SAMPLE_DATA);
  writeFileSync('test-poster.html', html);
  console.log(`HTML: ${html.length} chars → test-poster.html`);
  console.log('Open test-poster.html in your browser to preview the design.\n');

  // Try PNG rendering (needs Playwright + Chromium)
  try {
    const result = await renderToPng(SAMPLE_DATA);
    writeFileSync('test-poster.png', result.png);
    console.log(`PNG: ${result.png.length} bytes, ${result.width}x${result.height} → test-poster.png`);
  } catch (err) {
    console.log(`PNG rendering skipped (Playwright not available locally): ${err.message}`);
    console.log('The HTML preview is sufficient for design iteration.');
  }

  console.log('\n=== Done ===');
}

main().catch(err => {
  console.error('Failed:', err);
  process.exit(1);
});
