/**
 * Muddy's Top 10 Chart Poster — AntV Infographic Custom Template
 * 
 * Renders a 1280×720 chart poster with:
 * - Header: logo, chart title, week date range
 * - Chart: 10 ranked entries with artist, title, plays, movement
 * - Sidebar: chart story + stats
 * - Footer: show time, presenters, tagline
 * 
 * Uses renderToString for SSR (no browser needed).
 */
const { renderToString } = require('@antv/infographic/ssr');
const { Resvg } = require('@resvg/resvg-js');

const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 720;

/**
 * Build the AntV infographic syntax for the Muddy's Top 10 chart poster.
 * 
 * This uses the built-in list-row template with customised data structure.
 * For a fully custom layout, we'd register a custom structure — but the
 * built-in vertical list gives us a clean ranked list which is the core need.
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
  const svg = await renderToString(syntax, {
    width: options.width || CANVAS_WIDTH,
    height: options.height || CANVAS_HEIGHT,
    themeConfig: {
      colorPrimary: '#a855f7',
      colorBg: '#0a0014',
    }
  });
  return svg;
}

/**
 * Render chart data to PNG buffer at exactly 1280×720.
 */
async function renderToPng(data, options = {}) {
  const svg = await renderToSvg(data, options);
  
  // Force the SVG to 1280×720 by adjusting the root element attributes
  const targetWidth = CANVAS_WIDTH;
  const targetHeight = CANVAS_HEIGHT;
  const adjustedSvg = svg
    .replace(/width="[^"]*"/, `width="${targetWidth}"`)
    .replace(/height="[^"]*"/, `height="${targetHeight}"`);
  
  const resvg = new Resvg(adjustedSvg, {
    fitTo: { mode: 'width', value: targetWidth },
    background: '#0a0014'
  });
  
  const rendered = resvg.render();
  return {
    png: rendered.asPng(),
    width: rendered.width,
    height: rendered.height,
    svgLength: svg.length
  };
}

module.exports = {
  buildChartPosterSyntax,
  renderToSvg,
  renderToPng,
  CANVAS_WIDTH,
  CANVAS_HEIGHT
};
