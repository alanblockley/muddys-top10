/**
 * Muddy's Top 10 Chart Poster — HTML Template Renderer
 * 
 * Generates a 1280×720 infographic from structured chart data using
 * a built-in HTML/CSS template. Rendered to PNG via Playwright.
 * 
 * The template is defined here as a function of data — no AI authoring,
 * no external template files needed. Change the design by editing this file.
 */

const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 720;

/**
 * Build the complete HTML document for the chart poster.
 */
function buildPosterHtml(data) {
  const tracks = (data.tracks || []).slice(0, 10);
  const stats = data.stats || {};
  const show = data.show || {};

  const trackRows = tracks.map(t => {
    const movementClass = t.movement || 'same';
    const movementIcon = { up: '▲', down: '▼', new: '★', same: '—', reentry: '↺' }[t.movement] || '—';
    const deltaText = t.movement === 'up' ? `+${t.delta}` :
                      t.movement === 'down' ? `${t.delta}` :
                      t.movement === 'new' ? 'NEW' :
                      t.movement === 'reentry' ? 'RE-ENTRY' : '';

    return `<tr class="track-row ${movementClass}">
      <td class="rank">${t.rank}</td>
      <td class="track-info">
        <span class="artist">${escapeHtml(t.artist)}</span>
        <span class="title">${escapeHtml(t.title)}</span>
      </td>
      <td class="plays">${t.plays}</td>
      <td class="movement"><span class="movement-icon">${movementIcon}</span><span class="movement-delta">${deltaText}</span></td>
    </tr>`;
  }).join('\n');

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
  width: ${CANVAS_WIDTH}px;
  height: ${CANVAS_HEIGHT}px;
  overflow: hidden;
  background: #050008;
  font-family: 'Arial Narrow', 'Trebuchet MS', Arial, sans-serif;
  color: #f8fafc;
}
.poster {
  width: ${CANVAS_WIDTH}px;
  height: ${CANVAS_HEIGHT}px;
  display: grid;
  grid-template-rows: 90px 1fr 70px;
  background: radial-gradient(ellipse at 80% 0%, rgba(168,85,247,0.15), transparent 50%),
              radial-gradient(ellipse at 20% 100%, rgba(217,70,239,0.1), transparent 40%),
              linear-gradient(135deg, #050008 0%, #0a0020 50%, #020617 100%);
  padding: 16px 24px;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 2px solid rgba(168,85,247,0.5);
  padding-bottom: 12px;
}
.header-title {
  flex: 1;
}
.header-title h1 {
  font-size: 36px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  text-shadow: 0 2px 8px rgba(168,85,247,0.4);
}
.header-title h1 .accent { color: #a855f7; }
.header-week {
  text-align: right;
  border: 1px solid #a855f7;
  padding: 8px 14px;
  border-radius: 4px;
}
.header-week .date { font-size: 16px; font-weight: 700; color: #facc15; }
.header-week .headline { font-size: 11px; color: #e2e8f0; margin-top: 2px; }

/* Chart Table */
.chart-section {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 16px;
  padding: 12px 0;
  overflow: hidden;
}
.chart-table {
  width: 100%;
  border-collapse: collapse;
}
.track-row td {
  padding: 4px 8px;
  border-bottom: 1px solid rgba(168,85,247,0.2);
  vertical-align: middle;
}
.track-row .rank {
  font-size: 24px;
  font-weight: 900;
  width: 40px;
  text-align: center;
  color: #a855f7;
}
.track-row .track-info {
  padding-left: 8px;
}
.track-row .artist {
  display: block;
  font-size: 15px;
  font-weight: 800;
  color: #f8fafc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 420px;
}
.track-row .title {
  display: block;
  font-size: 13px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 420px;
}
.track-row .plays {
  font-size: 16px;
  font-weight: 700;
  color: #facc15;
  text-align: center;
  width: 50px;
}
.track-row .movement {
  width: 80px;
  text-align: center;
}
.track-row .movement-icon {
  font-size: 14px;
  margin-right: 4px;
}
.track-row .movement-delta {
  font-size: 12px;
  font-weight: 700;
}
.track-row.up .movement-icon, .track-row.up .movement-delta { color: #22c55e; }
.track-row.down .movement-icon, .track-row.down .movement-delta { color: #ef4444; }
.track-row.new .movement-icon, .track-row.new .movement-delta { color: #facc15; }
.track-row.same .movement-icon, .track-row.same .movement-delta { color: #94a3b8; }
.track-row.reentry .movement-icon, .track-row.reentry .movement-delta { color: #38bdf8; }

/* Sidebar */
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chart-story {
  background: rgba(168,85,247,0.08);
  border: 1px solid rgba(168,85,247,0.3);
  border-radius: 6px;
  padding: 12px;
}
.chart-story h3 {
  color: #facc15;
  font-size: 13px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.chart-story p {
  font-size: 12px;
  line-height: 1.4;
  color: #e2e8f0;
}
.stats-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.stat-box {
  background: rgba(0,0,0,0.4);
  border: 1px solid rgba(168,85,247,0.2);
  border-radius: 4px;
  padding: 8px;
  text-align: center;
}
.stat-box .stat-number {
  font-size: 22px;
  font-weight: 900;
  color: #facc15;
}
.stat-box .stat-label {
  font-size: 10px;
  text-transform: uppercase;
  color: #94a3b8;
}

/* Footer */
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 2px solid rgba(168,85,247,0.5);
  padding-top: 12px;
}
.footer-show {
  font-size: 14px;
}
.footer-show .day { color: #facc15; font-weight: 700; }
.footer-show .time { color: #a855f7; font-weight: 700; }
.footer-show .presenters { color: #e2e8f0; }
.footer-tagline {
  font-size: 13px;
  color: #a855f7;
  font-style: italic;
}
</style>
</head>
<body>
<div class="poster">
  <div class="header">
    <div class="header-title">
      <h1><span class="accent">Muddy's</span> ${escapeHtml(data.chart_title || 'Top 10')}</h1>
    </div>
    <div class="header-week">
      <div class="date">${escapeHtml(data.week_display || '')}</div>
      <div class="headline">${escapeHtml(data.headline || '')}</div>
    </div>
  </div>

  <div class="chart-section">
    <table class="chart-table">
      <tbody>
        ${trackRows}
      </tbody>
    </table>
    <div class="sidebar">
      <div class="chart-story">
        <h3>Chart Story</h3>
        <p>${escapeHtml(data.chart_story || '')}</p>
      </div>
      <div class="stats-panel">
        <div class="stat-box"><div class="stat-number">${stats.new_entries || 0}</div><div class="stat-label">New Entries</div></div>
        <div class="stat-box"><div class="stat-number">${stats.climbers || 0}</div><div class="stat-label">Climbers</div></div>
        <div class="stat-box"><div class="stat-number">${stats.fallers || 0}</div><div class="stat-label">Fallers</div></div>
        <div class="stat-box"><div class="stat-number">${stats.non_movers || 0}</div><div class="stat-label">Non-Movers</div></div>
      </div>
    </div>
  </div>

  <div class="footer">
    <div class="footer-show">
      <span class="day">${escapeHtml(show.day || 'EVERY SATURDAY')}</span>
      <span class="time">${escapeHtml(show.time || '2AM SLT')}</span>
      <span class="presenters">with ${escapeHtml(show.presenters || 'DJ TOOHEY & JP')}</span>
    </div>
    <div class="footer-tagline">${escapeHtml(data.tagline || 'Your requests. Your music. Your chart.')}</div>
  </div>
</div>
</body>
</html>`;
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Render chart data to PNG buffer at 1280×720 using Playwright.
 */
async function renderToPng(data, options = {}) {
  const trackCount = (data.tracks || []).length;
  console.log(`chart-poster renderToPng: ${trackCount} tracks, week=${data.week_id}, title=${data.chart_title}`);
  if (trackCount === 0) {
    console.warn('chart-poster: No tracks in data! PNG will be empty.');
  }

  const html = buildPosterHtml(data);

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
      htmlLength: html.length
    };
  } finally {
    await browser.close();
  }
}

module.exports = {
  buildPosterHtml,
  renderToPng,
  CANVAS_WIDTH,
  CANVAS_HEIGHT
};
