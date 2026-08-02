/**
 * Muddy's Top 10 Chart Poster — AntV Infographic Custom Template
 * 
 * Uses dynamic import() for @antv/infographic since it requires ESM (lodash-es).
 */
const { Resvg } = require('@resvg/resvg-js');

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
 * Uses dynamic import() since @antv/infographic requires ESM.
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
 * Render chart data to PNG buffer at exactly 1280×720.
 */
async function renderToPng(data, options = {}) {
  // Log what we received for debugging
  const trackCount = (data.tracks || []).length;
  console.log(`chart-poster renderToPng: ${trackCount} tracks, week=${data.week_id}, title=${data.chart_title}`);
  if (trackCount === 0) {
    console.warn('chart-poster: No tracks in data! PNG will be empty.');
  }

  const svg = await renderToSvg(data, options);
  
  // Extract original viewBox dimensions and scale to fill 1280x720
  const viewBoxMatch = svg.match(/viewBox="([^"]+)"/);
  let adjustedSvg = svg;
  if (viewBoxMatch) {
    // Keep the original viewBox (content coordinates) but set display size to 1280x720
    adjustedSvg = svg
      .replace(/width="[^"]*"/, `width="${CANVAS_WIDTH}"`)
      .replace(/height="[^"]*"/, `height="${CANVAS_HEIGHT}"`);
  }
  
  const resvg = new Resvg(adjustedSvg, {
    fitTo: { mode: 'width', value: CANVAS_WIDTH },
    background: '#0a0014'
  });
  
  const rendered = resvg.render();
  console.log(`chart-poster PNG: ${rendered.width}x${rendered.height}, ${rendered.asPng().length} bytes`);
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
