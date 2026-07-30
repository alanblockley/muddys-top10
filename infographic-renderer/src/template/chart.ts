import type { ChartBadge, ChartTalkIcon, ChartTalkItem, NormalizedRenderInput } from "../types.js";
import { escapeHtml, plural, signedPercentage } from "../helpers/formatting.js";
import { movementDisplay, movementSvg } from "../helpers/movement.js";
import { fitTextClass } from "../helpers/text-fit.js";

export function renderHtml(data: NormalizedRenderInput): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1280, initial-scale=1.0">
  <title>Muddy's Top 10</title>
  <link rel="stylesheet" href="./chart.css">
</head>
<body>
  <main id="infographic">
    ${renderHeader(data)}
    ${renderChart(data)}
    ${renderChartTalk(data)}
    ${renderStats(data)}
    ${renderBottom(data)}
    <div class="footer">YOUR REQUESTS. YOUR MUSIC. <span class="purple">YOUR CHART.</span><span class="star">★</span>THANK YOU FOR KEEPING MUDDY'S PLAYING!</div>
  </main>
</body>
</html>`;
}

function renderHeader(data: NormalizedRenderInput): string {
  return `<section class="header">
    <img class="logo" src="../../frontend/assets/muddys-logo.png" alt="Muddy's logo">
    <div class="title">MUDDY'S TOP 10 <span class="this-week">THIS WEEK</span></div>
    <div class="script">Music Cafe</div>
    <div class="week">${escapeHtml(data.week.display)}</div>
    <div class="neon-note">${musicNoteSvg()}</div>
    <div class="compiled">${escapeHtml(data.show.compiledFrom)}</div>
  </section>`;
}

function renderChart(data: NormalizedRenderInput): string {
  const badgesByPosition = new Map(data.chartBadges.map((badge) => [badge.position, badge]));
  const rows = data.chart.map((entry) => {
    const movement = movementDisplay(entry);
    const trackText = `${entry.artist} - ${entry.title}`;
    const badge = badgesByPosition.get(entry.position);
    return `<div class="chart-row">
      <div class="position">${entry.position}</div>
      <div class="track">
        ${badge ? renderChartBadge(badge) : ""}
        <div class="${fitTextClass(trackText, "track-title")}"><span class="artist">${escapeHtml(entry.artist)}</span> <span class="song">- ${escapeHtml(entry.title)}</span></div>
        <div class="plays">${plural(entry.plays, "play")}</div>
      </div>
      <div class="movement-icon ${movement.className}">${movementSvg(movement.symbol)}</div>
      <div class="movement-label ${movement.className}">${escapeHtml(movement.label)}</div>
    </div>`;
  }).join("");

  return `<section class="chart-panel">
    <div class="crown">${crownSvg()}</div>
    ${rows}
  </section>`;
}

function renderChartBadge(badge: ChartBadge): string {
  return `<div class="chart-badge badge-${escapeHtml(badge.tone ?? "feature")}">${escapeHtml(badge.label)}</div>`;
}

function renderChartTalk(data: NormalizedRenderInput): string {
  return `<section class="talk-panel layout-${escapeHtml(data.layout.variant)}">
    <div class="talk-title">CHART TALK</div>
    <div class="talk-grid">
      ${data.chartTalk.map((item) => renderChartTalkItem(item)).join("")}
    </div>
  </section>`;
}

function renderChartTalkItem(item: ChartTalkItem): string {
  const icon = item.icon ?? iconFromKind(item.kind);
  const isFeature = item.emphasis === "feature";
  const body = isFeature && item.short_body ? item.short_body : item.body;
  return `<article class="talk-cell ${isFeature ? "talk-feature" : ""}">
    <div class="talk-icon ${talkIconClass(icon)}">${talkIconSvg(icon)}</div>
    <h3>${escapeHtml(item.heading)}</h3>
    <p>${escapeHtml(body)}</p>
    ${isFeature ? renderFeatureMetrics(item) : ""}
  </article>`;
}

function renderFeatureMetrics(item: ChartTalkItem): string {
  const metrics = item.metrics ?? {};
  const artist = metrics.artist ?? "";
  const track = metrics.track ?? "";
  const movement = metrics.movement ?? metrics.places ?? "";
  if (!artist && !track && !movement) {
    return "";
  }
  return `<div class="feature-metric">
    ${artist ? `<div class="feature-artist">${escapeHtml(artist)}</div>` : ""}
    ${track ? `<div class="feature-track">${escapeHtml(track)}</div>` : ""}
    ${movement !== "" ? `<div class="feature-move">↑ ${escapeHtml(movement)}</div>` : ""}
  </div>`;
}

function renderStats(data: NormalizedRenderInput): string {
  const percentageClass = data.numbers.percentageChange < 0 ? "movement-down" : data.numbers.percentageChange > 0 ? "movement-up" : "movement-same";
  return `<section class="stats-row">
    <div class="stat-panel">
      <h3 class="stats-title">THIS WEEK'S STATS</h3>
      <div class="metric"><span class="mini-icon movement-new">★</span>${plural(data.stats.newEntries, "new entry", "new entries")}</div>
      <div class="metric"><span class="mini-icon movement-up">↑</span>${plural(data.stats.climbers, "climber")}</div>
      <div class="metric"><span class="mini-icon movement-down">↓</span>${plural(data.stats.fallers, "faller")}</div>
      <div class="metric"><span class="mini-icon movement-same">−</span>${plural(data.stats.nonMovers, "non-mover")}</div>
    </div>
    <div class="stat-panel">
      <h3 class="facts-title">CHART FACTS</h3>
      ${data.facts.map((fact) => `<div class="fact-line">${escapeHtml(fact)}</div>`).join("")}
    </div>
    <div class="stat-panel">
      <h3 class="numbers-title">TOP 10 BY THE NUMBERS</h3>
      <div class="number-line">${data.numbers.totalPlaysThisWeek} plays this week</div>
      <div class="number-line">${data.numbers.totalPlaysLastWeek} plays last week</div>
      <div class="number-line"><span class="${percentageClass}">${signedPercentage(data.numbers.percentageChange)}</span>&nbsp;week on week</div>
      <div class="number-line">${data.numbers.weeksSinceLaunch} weeks tracked · ${data.numbers.differentArtists} artists</div>
    </div>
  </section>`;
}

function renderBottom(data: NormalizedRenderInput): string {
  return `<div class="crowd"></div>
  <div class="mic">${microphoneSvg()}</div>
  <section class="bottom">
    <div class="countdown">
      <div class="catch">CATCH THE TOP 10</div>
      <div class="day">${escapeHtml(data.show.day)}</div>
      <div class="time">AT ${escapeHtml(data.show.time)}</div>
    </div>
    <div class="presenters">
      <div class="with">WITH</div>
      <div class="names">${escapeHtml(data.show.presenters)}</div>
      <div class="tagline-script">${escapeHtml(data.show.presenterTagline)}</div>
    </div>
    <div class="venue">
      <div class="join">JOIN US LIVE AT</div>
      <div class="venue-name">${escapeHtml(data.show.venueName)}</div>
      <div class="venue-tagline">${escapeHtml(data.show.venueTagline)}</div>
    </div>
    <div class="badge">
      <div>★</div>
      <div>YOUR REQUESTS.</div>
      <div>YOUR MUSIC.</div>
      <div class="purple">YOUR CHART.</div>
      <div>★</div>
    </div>
  </section>`;
}

function iconFromKind(kind: string): ChartTalkIcon {
  if (kind.includes("rocket")) return "rocket";
  if (kind.includes("climber")) return "climber";
  if (kind.includes("note")) return "note";
  if (kind.includes("music")) return "music";
  if (kind.includes("weeks") || kind.includes("long")) return "weeks";
  if (kind.includes("star") || kind.includes("new")) return "star";
  return "trophy";
}

function talkIconClass(icon: ChartTalkIcon): string {
  if (icon === "rocket") return "movement-down";
  if (icon === "climber") return "movement-reentry";
  if (icon === "note") return "movement-reentry";
  if (icon === "music") return "movement-up";
  if (icon === "weeks") return "movement-new";
  if (icon === "star") return "movement-new";
  return "movement-new";
}

function talkIconSvg(icon: ChartTalkIcon): string {
  if (icon === "rocket") {
    return `<svg viewBox="0 0 40 40"><path d="M31 3c-7 1-13 5-17 12l-7 1 6 6-2 8 8-2 6 6 1-7c7-4 11-10 12-17 1-5-2-8-7-7Zm-5 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8ZM8 28c-3 1-5 3-6 8 5-1 7-3 8-6Z"/></svg>`;
  }
  if (icon === "climber") {
    return `<svg viewBox="0 0 40 40"><path d="M6 32h6V20H6Zm11 0h6V13h-6Zm11 0h6V6h-6Z"/><path d="M7 14 18 8l7 5 8-10 3 10-10 1 3-4-4 6-7-5-9 5Z"/></svg>`;
  }
  if (icon === "note" || icon === "music") {
    return musicNoteSvg();
  }
  if (icon === "weeks") {
    return `<svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" stroke-width="3"/><text x="20" y="20" dominant-baseline="middle" text-anchor="middle" font-size="13" font-family="Impact" fill="currentColor">10</text></svg>`;
  }
  if (icon === "star") {
    return `<svg viewBox="0 0 40 40"><path d="m20 3 5 11 12 1-9 8 3 12-11-6-11 6 3-12-9-8 12-1Z"/></svg>`;
  }
  return `<svg viewBox="0 0 40 40"><path d="M11 35h18v-3H11Zm-4-5h26l-3-16-7 6-3-12-3 12-7-6Z"/></svg>`;
}

function musicNoteSvg(): string {
  return `<svg viewBox="0 0 64 64"><path d="M42 7v34a11 11 0 1 1-5-9V14l-22 4v29a11 11 0 1 1-5-9V14Z" fill="currentColor"/></svg>`;
}

function crownSvg(): string {
  return `<svg viewBox="0 0 40 40"><path fill="currentColor" d="M5 31h30v5H5Zm0-19 9 8 6-14 6 14 9-8-4 17H9Z"/></svg>`;
}

function microphoneSvg(): string {
  return `<svg viewBox="0 0 64 64"><path fill="none" stroke="currentColor" stroke-width="4" d="M32 6a12 12 0 0 0-12 12v17a12 12 0 0 0 24 0V18A12 12 0 0 0 32 6Z"/><path fill="none" stroke="currentColor" stroke-width="4" d="M14 32v3a18 18 0 0 0 36 0v-3M32 53v8M21 61h22M23 18h18M23 27h18M23 36h18"/></svg>`;
}
