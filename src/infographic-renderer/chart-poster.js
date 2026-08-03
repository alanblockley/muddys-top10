/**
 * Muddy's Top 10 Chart Poster — AntV Infographic Custom Template
 * 
 * Renders chart data via AntV Infographic SSR to SVG, then uses
 * Playwright (headless Chromium) to render the SVG to PNG since
 * the SVG uses foreignObject which requires a browser engine.
 */

const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 720;

/**
 * Build the AntV infographic syntax for the chart poster.
 */
function buildChartPosterSyntax(data) {
  const trackLines = data.tracks.map(t => {
    const movementIcon = {
      up: '▲',
      down: '▼',
      new: '★',
      same: '—',
      reentry: '↺'
    }[t.movement] || '';
    
    const deltaStr = t.movement === 'up' ? `+${t.delta}` :
                     t.movement === 'down' ? `${t.delta}` :
                     t.movement === 'new' ? 'NEW' :
                     t.movement === 'reentry' ? 'RE-ENTRY' :
                     '';

    return `    - label #${t.rank}  ${t.artist} — ${t.title}
      desc ${t.plays} plays  ${movementIcon} ${deltaStr}`;
  }).join('\n');

  const statsLine = `${data.stats.new_entries} new · ${data.stats.climbers} climbers · ${data.stats.fallers} fallers · ${data.stats.non_movers} non-movers`;

  return `infographic list-row-simple
theme dark
data
  title ${data.chart_title}
  description ${data.week_display} — ${data.headline}
  lists
${trackLines}
    - label ${data.show.day} ${data.show.time}
      desc ${data.show.presenters} · ${statsLine}
    - label ${data.tagline}
      desc ${data.chart_story}
`;
}

/**
 * Render chart data to SVG string using AntV Infographic SSR.
 */
async function renderToSvg(data, options = {}) {
  const syntax = buildChartPosterSyntax(data);
  const { renderToString } = await import('@antv/infographic/ssr');
  const svg = await renderToString(syntax, {
    width: options.width || CANVAS_WIDTH,
    height: options.height || CANVAS_HEIGHT,
  });
  return svg;
}

/**
 * Render chart data to PNG buffer at 1280×720 using Playwright.
 * 
 * AntV's SVG uses foreignObject (HTML-in-SVG) which requires a
 * browser engine to render text. resvg-js cannot handle this.
 */
async function renderToPng(data, options = {}) {
  const trackCount = (data.tracks || []).length;
  console.log(`chart-poster renderToPng: ${trackCount} tracks, week=${data.week_id}, title=${data.chart_title}`);
  if (trackCount === 0) {
    console.warn('chart-poster: No tracks in data! PNG will be empty.');
  }

  const svg = await renderToSvg(data, options);
  console.log(`chart-poster SVG: ${svg.length} chars`);

  // Wrap SVG in an HTML document for Playwright rendering
  const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: ${CANVAS_WIDTH}px; height: ${CANVAS_HEIGHT}px; overflow: hidden; background: #0a0014; }
#container { width: ${CANVAS_WIDTH}px; height: ${CANVAS_HEIGHT}px; display: flex; align-items: center; justify-content: center; }
#container svg { width: 100%; height: 100%; }
</style>
</head>
<body>
<div id="container">${svg}</div>
</body>
</html>`;

  // Render with Playwright
  const chromium = require('@sparticuz/chromium');
  const { chromium: playwrightChromium } = require('playwright-core');

  const browser = await playwrightChromium.launch({
    args: chromium.args,
    executablePath: await chromium.executablePath(),
    headless: true
  });

  try {
    const context = await browser.newContext({
      viewport: { width: CANVAS_WIDTH, height: CANVAS_HEIGHT },
      deviceScaleFactor: 1,
      javaScriptEnabled: false
    });
    const page = await context.newPage();
    await page.setContent(html, { waitUntil: 'domcontentloaded' });
    const png = await page.screenshot({ type: 'png' });
    await context.close();

    console.log(`chart-poster PNG: ${CANVAS_WIDTH}x${CANVAS_HEIGHT}, ${png.length} bytes`);
    return {
      png,
      width: CANVAS_WIDTH,
      height: CANVAS_HEIGHT,
      svgLength: svg.length
    };
  } finally {
    await browser.close();
  }
}

module.exports = {
  buildChartPosterSyntax,
  renderToSvg,
  renderToPng,
  CANVAS_WIDTH,
  CANVAS_HEIGHT
};
