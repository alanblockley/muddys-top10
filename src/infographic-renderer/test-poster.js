/**
 * Test the chart poster rendering with sample data.
 */
const { renderToPng, renderToSvg, buildChartPosterSyntax } = require('./chart-poster');
const { writeFileSync } = require('node:fs');
const { join } = require('node:path');

const SAMPLE_DATA = {
  chart_title: "Muddy's Top 10",
  tagline: "Your requests. Your music. Your chart.",
  week_display: "JUL 25 – AUG 1, 2026",
  headline: "New number one as Olivia Dean takes the crown",
  chart_story: "After three weeks climbing steadily, Olivia Dean finally reaches the summit. Bruno Mars drops two places after a dominant run.",
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

  // Show the syntax
  const syntax = buildChartPosterSyntax(SAMPLE_DATA);
  console.log('Generated syntax:');
  console.log(syntax);
  console.log('---\n');

  // Render to SVG
  console.log('Rendering SVG...');
  const svg = await renderToSvg(SAMPLE_DATA);
  writeFileSync(join(__dirname, 'test-poster.svg'), svg);
  console.log(`SVG: ${svg.length} chars → test-poster.svg`);

  // Render to PNG
  console.log('Rendering PNG...');
  const result = await renderToPng(SAMPLE_DATA);
  writeFileSync(join(__dirname, 'test-poster.png'), result.png);
  console.log(`PNG: ${result.png.length} bytes, ${result.width}x${result.height} → test-poster.png`);

  console.log('\n=== Done ===');
}

main().catch(err => {
  console.error('Failed:', err);
  process.exit(1);
});
