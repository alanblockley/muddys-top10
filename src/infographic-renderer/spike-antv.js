/**
 * Spike: AntV Infographic SSR rendering
 * 
 * Tests whether @antv/infographic can render a chart poster
 * server-side to SVG, and whether we can convert that to PNG.
 */
const { renderToString } = require('@antv/infographic/ssr');
const { Resvg } = require('@resvg/resvg-js');
const { writeFileSync } = require('node:fs');
const { join } = require('node:path');

const SAMPLE_DATA = {
  chart_title: "Muddy's Top 10",
  tagline: "Your requests. Your music. Your chart.",
  week_display: "JUL 25 – AUG 1, 2026",
  headline: "New number one as Olivia Dean takes the crown",
  chart_story: "After three weeks climbing, Olivia Dean finally takes the top spot.",
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

// Build the AntV infographic syntax for a ranked list
function buildChartSyntax(data) {
  const trackLines = data.tracks.map(t => {
    const movementIcon = { up: '↑', down: '↓', new: '★', same: '—', reentry: '↺' }[t.movement] || '';
    const deltaStr = t.delta ? ` (${t.delta > 0 ? '+' : ''}${t.delta})` : '';
    return `    - label #${t.rank} ${t.artist}
      desc ${t.title} • ${t.plays} plays ${movementIcon}${deltaStr}`;
  }).join('\n');

  return `infographic list-col-simple
theme dark
data
  title ${data.chart_title} — ${data.week_display}
  description ${data.headline}
  lists
${trackLines}
`;
}

async function main() {
  console.log('=== AntV Infographic SSR Spike ===\n');

  // Step 1: Build syntax
  const syntax = buildChartSyntax(SAMPLE_DATA);
  console.log('Syntax:\n', syntax.slice(0, 300), '...\n');

  // Step 2: Render to SVG
  console.log('Rendering to SVG...');
  let svg;
  try {
    svg = await renderToString(syntax);
    console.log(`SVG generated: ${svg.length} characters`);
    writeFileSync(join(__dirname, 'spike-output.svg'), svg);
    console.log('Saved: spike-output.svg');
  } catch (err) {
    console.error('renderToString failed:', err.message);
    console.error(err.stack);
    process.exit(1);
  }

  // Step 3: Convert SVG to PNG
  console.log('\nConverting SVG to PNG (1280x720)...');
  try {
    const resvg = new Resvg(svg, {
      fitTo: { mode: 'width', value: 1280 },
      background: '#000000'
    });
    const pngData = resvg.render();
    const pngBuffer = pngData.asPng();
    writeFileSync(join(__dirname, 'spike-output.png'), pngBuffer);
    console.log(`PNG generated: ${pngBuffer.length} bytes`);
    console.log(`Dimensions: ${pngData.width}x${pngData.height}`);
    console.log('Saved: spike-output.png');
  } catch (err) {
    console.error('SVG to PNG conversion failed:', err.message);
    console.error(err.stack);
    process.exit(1);
  }

  console.log('\n=== Spike complete ===');
  console.log('Check spike-output.svg and spike-output.png for quality assessment.');
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
