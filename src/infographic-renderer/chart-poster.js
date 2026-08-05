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
  const branding = data.branding || {};
  const primary = branding.primary_color || '${primary}';
  const secondary = branding.secondary_color || '${secondary}';
  const accent = branding.accent_color || '${accent}';
  const bgColor = branding.background_color || '#050005';
  const textColor = branding.text_color || '${textColor}';

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
        <span class="artist">${escapeHtml(t.artist)}</span><span class="title">${escapeHtml(t.title)}</span>
      </td>
      <td class="plays">${t.plays}<span class="plays-label">plays</span></td>
      <td class="movement"><span class="movement-icon">${movementIcon}</span><span class="movement-delta">${deltaText}</span></td>
    </tr>`;
  }).join('\n');

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
@font-face { font-family: 'Font Awesome 6 Free'; font-style: normal; font-weight: 900; src: url('${data.fa_font_url || 'assets/fontawesome/webfonts/fa-solid-900.woff2'}') format('woff2'); }
.fa-solid, .fas { font-family: 'Font Awesome 6 Free'; font-weight: 900; font-style: normal; -webkit-font-smoothing: antialiased; }
.fa-trophy:before { content: "\\f091"; }
.fa-rocket:before { content: "\\f135"; }
.fa-star:before { content: "\\f005"; }
.fa-music:before { content: "\\f001"; }
.fa-fire:before { content: "\\f06d"; }
.fa-arrow-up:before { content: "\\f062"; }
.fa-arrow-down:before { content: "\\f063"; }
.fa-chart-line:before { content: "\\f201"; }
.fa-rotate-left:before { content: "\\f2ea"; }
.fa-equals:before { content: "\\f52c"; }
.fa-bolt:before { content: "\\f0e7"; }
.fa-crown:before { content: "\\f521"; }
.fa-users:before { content: "\\f0c0"; }
.fa-clock:before { content: "\\f017"; }
.fa-hashtag:before { content: "\\23"; }

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
  width: ${CANVAS_WIDTH}px;
  height: ${CANVAS_HEIGHT}px;
  overflow: hidden;
  background: #050008;
  font-family: 'Arial Narrow', 'Trebuchet MS', Arial, sans-serif;
  color: ${textColor};
}
.poster {
  width: ${CANVAS_WIDTH}px;
  height: ${CANVAS_HEIGHT}px;
  display: grid;
  grid-template-rows: 140px 1fr 100px;
  background: url('${data.background_url || 'assets/background.png'}') center/cover no-repeat;
  padding: 16px 24px 18px 24px;
  position: relative;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 2px solid rgba(168,85,247,0.5);
  padding-bottom: 12px;
}
.header-logo {
  width: 127px;
  height: 127px;
  object-fit: contain;
  filter: drop-shadow(0 0 8px rgba(168,85,247,0.5));
  position: absolute;
  top: 12px;
  left: 16px;
  z-index: 10;
}
.header-title {
  flex: 1;
  padding-left: 145px;
}
.header-title h1 {
  font-size: 42px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: 'Arial Black', 'Arial Narrow', 'Impact', sans-serif;
  color: ${textColor};
  text-shadow: 0 2px 12px rgba(168,85,247,0.5);
}
.header-title h1 .venue-name {
  display: block;
  font-family: 'Segoe Script', 'Brush Script MT', 'Lucida Handwriting', cursive;
  font-size: 36px;
  font-weight: 700;
  text-transform: none;
  letter-spacing: 0.01em;
  color: ${secondary};
  text-shadow: 0 0 10px rgba(250,204,21,0.3);
}
.header-title h1 .chart-name {
  display: block;
  font-family: 'Arial Black', 'Impact', sans-serif;
  font-size: 32px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: ${textColor};
  text-shadow: 0 2px 12px rgba(168,85,247,0.5);
}
.header-title .subtitle {
  font-size: 16px;
  font-weight: 700;
  color: ${secondary};
  text-transform: none;
  letter-spacing: 0.02em;
  margin-top: -8px;
  font-family: 'Trebuchet MS', sans-serif;
  text-shadow: 0 0 10px rgba(250,204,21,0.4);
  text-align: center;
  position: absolute;
  left: 0;
  right: 0;
}
.header-title .subtitle::before {
  content: '✦ ';
  color: ${primary};
}
.header-title .subtitle::after {
  content: ' ✦';
  color: ${primary};
}
.header-title h1 .accent { color: ${primary}; }
.header-week {
  text-align: right;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
}
.header-week .tagline-accent {
  display: block;
  height: 2px;
  background: linear-gradient(90deg, transparent, ${primary}, ${secondary});
  margin: 8px 0;
  border-radius: 1px;
}
.header-week .tagline {
  font-size: 22px;
  font-weight: 700;
  color: ${secondary};
  font-style: italic;
  letter-spacing: 0.02em;
}
.header-week .headline { font-size: 11px; color: #e2e8f0; margin-top: 2px; }

/* Chart Table */
.chart-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 12px 0;
  overflow: visible;
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
  font-size: 22px;
  font-weight: 900;
  width: 44px;
  height: 36px;
  text-align: center;
  color: #ffffff;
  background: linear-gradient(135deg, ${primary}, #6d28d9);
  border-radius: 4px;
  line-height: 36px;
}
.track-row .track-info {
  padding-left: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.track-row .artist {
  font-size: 19px;
  font-weight: 800;
  color: ${primary};
}
.track-row .title {
  font-size: 19px;
  color: ${textColor};
  margin-left: 8px;
}
.track-row .plays {
  font-size: 16px;
  font-weight: 700;
  color: ${secondary};
  text-align: center;
  width: 42px;
  line-height: 1.1;
}
.track-row .plays-label {
  display: block;
  font-size: 8px;
  color: #94a3b8;
  text-transform: uppercase;
  font-weight: 600;
}
.track-row .movement {
  width: 110px;
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
.track-row.new .movement-icon, .track-row.new .movement-delta { color: ${secondary}; }
.track-row.same .movement-icon, .track-row.same .movement-delta { color: #94a3b8; }
.track-row.reentry .movement-icon, .track-row.reentry .movement-delta { color: #38bdf8; }

/* Sidebar */
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chart-talk-header {
  text-align: center;
  font-size: 18px;
  font-weight: 900;
  color: ${secondary};
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: linear-gradient(90deg, transparent 10%, rgba(250,204,21,0.15) 50%, transparent 90%);
  padding: 4px 0;
}
.chart-talk-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr 1fr;
  gap: 0;
  border: 1px solid rgba(168,85,247,0.4);
  flex: 1;
}
.chart-talk-cell {
  border-bottom: 1px dotted rgba(168,85,247,0.3);
  border-right: 1px dotted rgba(168,85,247,0.3);
  padding: 6px 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.chart-talk-cell:nth-child(2n) {
  border-right: none;
}
.chart-talk-cell:nth-child(n+5) {
  border-bottom: none;
}
.chart-talk-cell .cell-icon {
  font-size: 24px;
  line-height: 1;
  flex-shrink: 0;
  color: ${secondary};
  text-shadow: 0 0 6px rgba(250,204,21,0.4);
  width: 30px;
  text-align: center;
}
.chart-talk-cell .cell-text {
  font-size: 16px;
  line-height: 1.3;
  color: #e2e8f0;
  font-family: Arial, Helvetica, sans-serif;
}
.chart-talk-cell .cell-text strong {
  color: ${secondary};
  font-size: 13px;
  letter-spacing: 0.03em;
}
.stats-strip {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 0;
  border: 1px solid rgba(168,85,247,0.4);
}
.stats-strip-panel {
  padding: 6px 8px;
  border-right: 1px solid rgba(168,85,247,0.3);
  text-align: center;
}
.stats-strip-panel:last-child {
  border-right: none;
}
.stats-strip-panel .panel-title {
  font-size: 9px;
  font-weight: 700;
  color: ${secondary};
  text-transform: uppercase;
  margin-bottom: 4px;
}
.stats-strip-panel .panel-row {
  font-size: 11px;
  color: #e2e8f0;
  line-height: 1.5;
}
.stats-strip-panel .panel-row .icon { margin-right: 4px; }

/* Footer */
.footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  border-top: 2px solid rgba(168,85,247,0.5);
  padding-top: 12px;
}
.footer-show {
  text-align: center;
  line-height: 1.0;
}
.footer-show .line1 {
  font-size: 16px;
  color: #e2e8f0;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: -2px;
}
.footer-show .line2 {
  font-size: 26px;
  color: ${secondary};
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-shadow: 0 0 12px rgba(250,204,21,0.4);
  margin-bottom: -4px;
}
.footer-show .line3 {
  font-size: 32px;
  color: #ffffff;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  text-shadow: 0 2px 10px rgba(168,85,247,0.6);
}
.footer-compiled {
  font-size: 16px;
  color: ${secondary};
  font-style: italic;
  font-weight: 700;
  text-align: right;
  display: flex;
  flex-direction: column;
  justify-content: center;
  letter-spacing: 0.02em;
  margin-left: auto;
}
.footer-compiled .compiled-accent {
  display: block;
  height: 2px;
  background: linear-gradient(90deg, transparent, ${primary}, ${secondary});
  margin: 8px 0;
  border-radius: 1px;
}
.footer-divider {
  width: 3px;
  align-self: stretch;
  background: linear-gradient(180deg, ${primary}, ${secondary});
  margin: 0 20px;
  border-radius: 2px;
}
.footer-hosts {
  text-align: left;
}
.footer-hosts .hosts-with {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: 'Arial Black', 'Impact', sans-serif;
}
.footer-hosts .hosts-names {
  font-size: 22px;
  font-weight: 900;
  color: ${textColor};
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: 'Arial Black', 'Impact', sans-serif;
}
.footer-hosts .hosts-tagline1 {
  font-size: 16px;
  font-weight: 700;
  color: ${secondary};
  font-family: 'Segoe Script', 'Brush Script MT', 'Lucida Handwriting', cursive;
  text-shadow: 0 0 8px rgba(250,204,21,0.3);
}
.footer-hosts .hosts-tagline2 {
  font-size: 16px;
  font-weight: 700;
  color: ${secondary};
  font-family: 'Segoe Script', 'Brush Script MT', 'Lucida Handwriting', cursive;
  text-shadow: 0 0 8px rgba(250,204,21,0.3);
}
</style>
</head>
<body>
<div class="poster">
  <div class="header">
    <img class="header-logo" src="${escapeHtml(data.logo_url || 'assets/muddys-logo.png')}" alt="Muddy's Music Cafe">
    <div class="header-title">
      <h1><span class="venue-name">Muddy's Music Cafe</span><span class="chart-name">Top 10</span></h1>
      <div class="subtitle">This Week - ${escapeHtml(data.week_display || '')}</div>
    </div>
    <div class="header-week">
      <span class="tagline-accent"></span>
      <div class="tagline">${escapeHtml(data.tagline || 'Your requests. Your music. Your chart.')}</div>
      <span class="tagline-accent"></span>
    </div>
  </div>

  <div class="chart-section">
    <table class="chart-table">
      <tbody>
        ${trackRows}
      </tbody>
    </table>
    <div class="sidebar">
      <div class="chart-talk-header">Chart Talk</div>
      <div class="chart-talk-grid">
        ${buildChartTalkCells(data)}
      </div>
      <div class="stats-strip">
        <div class="stats-strip-panel">
          <div class="panel-title">Chart Story</div>
          <div class="panel-row" style="font-weight:700;color:${secondary};">${escapeHtml(data.headline || '')}</div>
          <div class="panel-row">${escapeHtml(data.chart_story || '')}</div>
        </div>
        <div class="stats-strip-panel">
          <div class="panel-title">This Week's Stats</div>
          <div class="panel-row"><span class="icon" style="color:${secondary}">★</span>${stats.new_entries || 0} new entries</div>
          <div class="panel-row"><span class="icon" style="color:#22c55e">▲</span>${stats.climbers || 0} climbers</div>
          <div class="panel-row"><span class="icon" style="color:#ef4444">▼</span>${stats.fallers || 0} fallers</div>
          <div class="panel-row"><span class="icon" style="color:#94a3b8">—</span>${stats.non_movers || 0} non-movers</div>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">
    <div class="footer-show">
      <div class="line1">Catch the Top 10</div>
      <div class="line2">Every Saturday</div>
      <div class="line3">At 2AM SLT</div>
    </div>
    <div class="footer-divider"></div>
    <div class="footer-hosts">
      <div class="hosts-with">With</div>
      <div class="hosts-names">DJ Toohey &amp; JP</div>
      <div class="hosts-tagline1">The Australian Dynamic Duo</div>
    </div>
    <div class="footer-compiled">
      <span class="compiled-accent"></span>
      Compiled from songs played by our DJs and patron requests
      <span class="compiled-accent"></span>
    </div>
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

function buildChartTalkCells(data) {
  // Use Claude-generated chart_talk if available
  const chartTalk = data.chart_talk || [];
  if (chartTalk.length >= 6) {
    return chartTalk.slice(0, 6).map(cell => 
      `<div class="chart-talk-cell"><span class="cell-icon"><i class="fa-solid ${escapeHtml(cell.icon || 'fa-music')}"></i></span><span class="cell-text"><strong>${escapeHtml(cell.headline || '')}</strong><br>${escapeHtml(cell.body || '')}</span></div>`
    ).join('\n');
  }

  // Fallback: auto-generate from chart data (no duplicate artists, no filler)
  const tracks = data.tracks || [];
  const cells = [];
  const usedArtists = new Set();

  function addCell(icon, headline, body, artist) {
    if (artist && usedArtists.has(artist)) return false;
    if (artist) usedArtists.add(artist);
    cells.push({ icon, headline, body });
    return true;
  }

  // 1. Chart leader
  const top = tracks[0];
  if (top) {
    if (top.movement === 'up') addCell('fa-trophy', 'TAKES #1!', `${top.artist} climbs ${top.delta} places to claim the top spot`, top.artist);
    else if (top.movement === 'new') addCell('fa-trophy', 'STRAIGHT IN AT #1!', `${top.artist} debuts at the top of the chart`, top.artist);
    else addCell('fa-trophy', 'HOLDS THE CROWN!', `${top.artist} keeps the #1 spot for another week`, top.artist);
  }

  // 2. Biggest climber (not #1 artist)
  const climbers = tracks.filter(t => t.movement === 'up' && t.delta && !usedArtists.has(t.artist));
  if (climbers.length) {
    const biggest = climbers.reduce((a, b) => (b.delta > a.delta ? b : a));
    addCell('fa-rocket', `UP ${biggest.delta} PLACES!`, `${biggest.artist} rockets to #${biggest.rank}`, biggest.artist);
  }

  // 3. New entry
  const newEntries = tracks.filter(t => t.movement === 'new' && !usedArtists.has(t.artist));
  if (newEntries.length) {
    addCell('fa-star', 'NEW ENTRY!', `${newEntries[0].artist} arrives at #${newEntries[0].rank}`, newEntries[0].artist);
  }

  // 4. Re-entry
  const reentries = tracks.filter(t => t.movement === 'reentry' && !usedArtists.has(t.artist));
  if (reentries.length) {
    addCell('fa-rotate-left', 'WELCOME BACK!', `${reentries[0].artist} returns at #${reentries[0].rank}`, reentries[0].artist);
  }

  // 5. Biggest faller
  const fallers = tracks.filter(t => t.movement === 'down' && t.delta && !usedArtists.has(t.artist));
  if (fallers.length) {
    const biggest = fallers.reduce((a, b) => (Math.abs(b.delta) > Math.abs(a.delta) ? b : a));
    addCell('fa-arrow-down', 'GIVES UP GROUND', `${biggest.artist} drops ${Math.abs(biggest.delta)} to #${biggest.rank}`, biggest.artist);
  }

  // 6. Non-mover
  const holds = tracks.filter(t => t.movement === 'same' && !usedArtists.has(t.artist));
  if (holds.length) {
    addCell('fa-equals', 'HOLDS STEADY!', `${holds[0].artist} stays put at #${holds[0].rank}`, holds[0].artist);
  }

  // 7. Second climber or another track story
  if (cells.length < 6) {
    const moreClimbers = tracks.filter(t => t.movement === 'up' && t.delta && !usedArtists.has(t.artist));
    if (moreClimbers.length) {
      const next = moreClimbers[0];
      addCell('fa-arrow-up', 'ON THE RISE!', `${next.artist} climbs ${next.delta} to #${next.rank}`, next.artist);
    }
  }

  // 8. Longest-running track
  if (cells.length < 6) {
    const withWeeks = tracks.filter(t => t.weeks_on_chart && t.weeks_on_chart > 1 && !usedArtists.has(t.artist));
    if (withWeeks.length) {
      const longest = withWeeks.reduce((a, b) => ((b.weeks_on_chart || 0) > (a.weeks_on_chart || 0) ? b : a));
      addCell('fa-clock', `${longest.weeks_on_chart} WEEKS!`, `${longest.artist} now in week ${longest.weeks_on_chart} on the chart`, longest.artist);
    }
  }

  // 9. Another faller or track at a new peak
  if (cells.length < 6) {
    const newPeaks = tracks.filter(t => t.best_rank && t.rank <= t.best_rank && t.movement === 'up' && !usedArtists.has(t.artist));
    if (newPeaks.length) {
      addCell('fa-crown', 'NEW PEAK!', `${newPeaks[0].artist} reaches their highest ever position at #${newPeaks[0].rank}`, newPeaks[0].artist);
    } else {
      const moreFallers = tracks.filter(t => t.movement === 'down' && !usedArtists.has(t.artist));
      if (moreFallers.length) {
        addCell('fa-arrow-down', 'SLIPS BACK', `${moreFallers[0].artist} eases to #${moreFallers[0].rank}`, moreFallers[0].artist);
      }
    }
  }

  // 10. Any remaining track not yet covered
  if (cells.length < 6) {
    const unused = tracks.filter(t => !usedArtists.has(t.artist));
    if (unused.length) {
      const t = unused[0];
      addCell('fa-music', `#${t.rank} THIS WEEK`, `${t.artist} sits at #${t.rank} with ${t.plays} plays`, t.artist);
    }
  }

  return cells.slice(0, 6).map(cell => 
    `<div class="chart-talk-cell"><span class="cell-icon"><i class="fa-solid ${escapeHtml(cell.icon)}"></i></span><span class="cell-text"><strong>${escapeHtml(cell.headline)}</strong><br>${escapeHtml(cell.body)}</span></div>`
  ).join('\n');
}

function totalPlays(data) {
  return (data.tracks || []).reduce((sum, t) => sum + (t.plays || 0), 0);
}

function formatWeekDate(weekId) {
  if (!weekId) return '';
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const parts = String(weekId).split('-');
  if (parts.length !== 3) return weekId;
  // week_id is the start date — closing date is 7 days later
  const startDate = new Date(parseInt(parts[0]), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
  const closingDate = new Date(startDate.getTime() + 7 * 24 * 60 * 60 * 1000);
  const day = closingDate.getDate();
  const month = months[closingDate.getMonth()];
  const year = closingDate.getFullYear();
  return `${day} ${month} ${year}`;
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

  // Resolve images as data URIs for Lambda (relative paths won't work in /var/task)
  const { readFileSync } = require('node:fs');
  const { join } = require('node:path');

  const logoPath = join(__dirname, 'assets', 'muddys-logo.png');
  const bgPath = join(__dirname, 'assets', 'background.png');
  const faFontPath = join(__dirname, 'assets', 'fontawesome', 'webfonts', 'fa-solid-900.woff2');

  let logoDataUri = data.logo_url || 'assets/muddys-logo.png';
  let bgDataUri = 'assets/background.png';
  let faFontDataUri = 'assets/fontawesome/webfonts/fa-solid-900.woff2';

  try {
    const logoBuffer = readFileSync(logoPath);
    logoDataUri = `data:image/png;base64,${logoBuffer.toString('base64')}`;
  } catch (e) {
    console.warn('chart-poster: Could not read logo file, using fallback path');
  }

  try {
    const bgBuffer = readFileSync(bgPath);
    bgDataUri = `data:image/png;base64,${bgBuffer.toString('base64')}`;
  } catch (e) {
    console.warn('chart-poster: Could not read background file, using fallback path');
  }

  try {
    const faBuffer = readFileSync(faFontPath);
    faFontDataUri = `data:font/woff2;base64,${faBuffer.toString('base64')}`;
  } catch (e) {
    console.warn('chart-poster: Could not read FA font file, using fallback path');
  }

  const renderData = { ...data, logo_url: logoDataUri, background_url: bgDataUri, fa_font_url: faFontDataUri };
  const html = buildPosterHtml(renderData);

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
      htmlLength: html.length,
      html
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
