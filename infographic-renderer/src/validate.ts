import type { ChartBadge, ChartEntry, ChartTalkIcon, ChartTalkItem, LayoutVariant, NormalizedRenderInput, RenderInput } from "./types.js";

const defaultShow: NormalizedRenderInput["show"] = {
  time: "2AM SLT",
  day: "EVERY SATURDAY",
  presenters: "DJ TOOHEY & JP",
  presenterTagline: "The Australian Dynamic Duo!",
  venueName: "MUDDY'S MUSIC CAFE",
  venueTagline: "WHERE MUSIC & FRIENDS COME TOGETHER",
  compiledFrom: "COMPILED FROM SONGS PLAYED BY OUR DJS AND PATRON REQUESTS"
};

const defaultLayout: NormalizedRenderInput["layout"] = {
  variant: "standard"
};

const layoutVariants = new Set<LayoutVariant>(["standard", "feature-climber", "feature-number-one", "feature-long-run"]);
const chartTalkIcons = new Set<ChartTalkIcon>(["trophy", "rocket", "star", "note", "music", "weeks", "climber"]);

export function validateInput(input: unknown): NormalizedRenderInput {
  if (!isRecord(input)) {
    throw new Error("input must be a JSON object");
  }

  validateLayout(input.layout);
  validateWeek(input.week);
  validateChart(input.chart);
  validateChartTalk(input.chartTalk);
  validateChartBadges(input.chartBadges);
  validateStats(input.stats);
  validateFacts(input.facts);
  validateNumbers(input.numbers);
  validateShow(input.show);

  const normalized = input as unknown as RenderInput;
  return {
    ...normalized,
    layout: {
      ...defaultLayout,
      ...(normalized.layout ?? {})
    },
    chart: [...normalized.chart].sort((a, b) => a.position - b.position),
    chartTalk: [...normalized.chartTalk].sort((a, b) => a.slot - b.slot),
    chartBadges: [...(normalized.chartBadges ?? [])],
    show: {
      ...defaultShow,
      ...(normalized.show ?? {})
    }
  };
}

export function blankInput(): NormalizedRenderInput {
  return {
    layout: defaultLayout,
    week: { start: "", end: "", display: "" },
    chart: Array.from({ length: 10 }, (_, index) => ({
      position: index + 1,
      artist: "",
      title: "",
      plays: 0,
      movement: { type: "same" as const, places: 0 }
    })),
    chartTalk: Array.from({ length: 6 }, (_, index) => ({
      slot: index + 1,
      kind: ["trophy", "rocket", "star", "note", "music", "weeks"][index],
      icon: ["trophy", "rocket", "star", "note", "music", "weeks"][index] as ChartTalkIcon,
      emphasis: "normal",
      heading: "",
      body: ""
    })),
    chartBadges: [],
    stats: { newEntries: 0, climbers: 0, fallers: 0, nonMovers: 0 },
    facts: ["", "", ""],
    numbers: {
      totalPlaysThisWeek: 0,
      totalPlaysLastWeek: 0,
      percentageChange: 0,
      weeksSinceLaunch: 0,
      differentArtists: 0
    },
    show: defaultShow
  };
}

function validateLayout(value: unknown): void {
  if (value === undefined) return;
  if (!isRecord(value)) throw new Error("layout must be an object");
  if (value.variant !== undefined && (typeof value.variant !== "string" || !layoutVariants.has(value.variant as LayoutVariant))) {
    throw new Error("layout.variant must be one of: standard, feature-climber, feature-number-one, feature-long-run");
  }
  if (value.featured_story !== undefined) requireString(value.featured_story, "layout.featured_story");
}

function validateWeek(value: unknown): void {
  if (!isRecord(value)) throw new Error("week must be an object");
  requireString(value.start, "week.start");
  requireString(value.end, "week.end");
  requireString(value.display, "week.display");
}

function validateChart(value: unknown): asserts value is ChartEntry[] {
  if (!Array.isArray(value)) throw new Error("chart must be an array");
  if (value.length !== 10) throw new Error("chart must contain exactly 10 entries");

  const positions = new Set<number>();
  for (const [index, entry] of value.entries()) {
    if (!isRecord(entry)) throw new Error(`chart[${index}] must be an object`);
    const position = requireInteger(entry.position, `chart[${index}].position`);
    if (position < 1 || position > 10) throw new Error(`chart[${index}].position must be between 1 and 10`);
    if (positions.has(position)) throw new Error(`chart positions must be unique; duplicate ${position}`);
    positions.add(position);
    requireString(entry.artist, `chart[${index}].artist`);
    requireString(entry.title, `chart[${index}].title`);
    const plays = requireInteger(entry.plays, `chart[${index}].plays`);
    if (plays < 0) throw new Error(`chart[${index}].plays must be non-negative`);
    validateMovement(entry.movement, `chart[${index}].movement`);
  }
}

function validateMovement(value: unknown, path: string): void {
  if (!isRecord(value)) throw new Error(`${path} must be an object`);
  const allowed = new Set(["new", "up", "down", "same", "reentry"]);
  if (typeof value.type !== "string" || !allowed.has(value.type)) {
    throw new Error(`${path}.type must be one of: new, up, down, same, reentry`);
  }
  if (value.type === "up" || value.type === "down") {
    const places = requireInteger(value.places, `${path}.places`);
    if (places < 1) throw new Error(`${path}.places must be greater than zero for ${value.type}`);
  }
}

function validateChartTalk(value: unknown): asserts value is ChartTalkItem[] {
  if (!Array.isArray(value)) throw new Error("chartTalk must be an array");
  if (value.length !== 6) throw new Error("chartTalk must contain exactly 6 items");
  const slots = new Set<number>();
  for (const [index, item] of value.entries()) {
    if (!isRecord(item)) throw new Error(`chartTalk[${index}] must be an object`);
    const slot = requireInteger(item.slot, `chartTalk[${index}].slot`);
    if (slot < 1 || slot > 6) throw new Error(`chartTalk[${index}].slot must be between 1 and 6`);
    if (slots.has(slot)) throw new Error(`chartTalk slots must be unique; duplicate ${slot}`);
    slots.add(slot);
    requireString(item.kind, `chartTalk[${index}].kind`);
    if (item.icon !== undefined && (typeof item.icon !== "string" || !chartTalkIcons.has(item.icon as ChartTalkIcon))) {
      throw new Error(`chartTalk[${index}].icon must be one of: trophy, rocket, star, note, music, weeks, climber`);
    }
    if (item.emphasis !== undefined && item.emphasis !== "normal" && item.emphasis !== "feature") {
      throw new Error(`chartTalk[${index}].emphasis must be normal or feature`);
    }
    requireString(item.heading, `chartTalk[${index}].heading`);
    requireString(item.body, `chartTalk[${index}].body`);
    if (item.short_body !== undefined) requireString(item.short_body, `chartTalk[${index}].short_body`);
    validateMetrics(item.metrics, `chartTalk[${index}].metrics`);
  }
}

function validateChartBadges(value: unknown): asserts value is ChartBadge[] | undefined {
  if (value === undefined) return;
  if (!Array.isArray(value)) throw new Error("chartBadges must be an array");
  const positions = new Set<number>();
  for (const [index, badge] of value.entries()) {
    if (!isRecord(badge)) throw new Error(`chartBadges[${index}] must be an object`);
    const position = requireInteger(badge.position, `chartBadges[${index}].position`);
    if (position < 1 || position > 10) throw new Error(`chartBadges[${index}].position must be between 1 and 10`);
    if (positions.has(position)) throw new Error(`chartBadges positions must be unique; duplicate ${position}`);
    positions.add(position);
    requireString(badge.label, `chartBadges[${index}].label`);
    if (badge.tone !== undefined && !["new", "up", "down", "feature"].includes(String(badge.tone))) {
      throw new Error(`chartBadges[${index}].tone must be one of: new, up, down, feature`);
    }
  }
}

function validateMetrics(value: unknown, path: string): void {
  if (value === undefined) return;
  if (!isRecord(value)) throw new Error(`${path} must be an object`);
  for (const [key, metric] of Object.entries(value)) {
    if (typeof metric !== "string" && typeof metric !== "number") {
      throw new Error(`${path}.${key} must be a string or number`);
    }
  }
}

function validateStats(value: unknown): void {
  if (!isRecord(value)) throw new Error("stats must be an object");
  for (const key of ["newEntries", "climbers", "fallers", "nonMovers"]) {
    const number = requireInteger(value[key], `stats.${key}`);
    if (number < 0) throw new Error(`stats.${key} must be non-negative`);
  }
}

function validateFacts(value: unknown): asserts value is string[] {
  if (!Array.isArray(value)) throw new Error("facts must be an array");
  if (value.length !== 3) throw new Error("facts must contain exactly 3 items");
  value.forEach((fact, index) => requireString(fact, `facts[${index}]`));
}

function validateNumbers(value: unknown): void {
  if (!isRecord(value)) throw new Error("numbers must be an object");
  for (const key of ["totalPlaysThisWeek", "totalPlaysLastWeek", "weeksSinceLaunch", "differentArtists"]) {
    const number = requireInteger(value[key], `numbers.${key}`);
    if (number < 0) throw new Error(`numbers.${key} must be non-negative`);
  }
  if (typeof value.percentageChange !== "number" || !Number.isFinite(value.percentageChange)) {
    throw new Error("numbers.percentageChange must be a finite number");
  }
}

function validateShow(value: unknown): void {
  if (value === undefined) return;
  if (!isRecord(value)) throw new Error("show must be an object");
  for (const key of ["time", "day", "presenters", "presenterTagline", "venueName", "venueTagline", "compiledFrom"]) {
    if (value[key] !== undefined) requireString(value[key], `show.${key}`);
  }
}

function requireString(value: unknown, path: string): string {
  if (typeof value !== "string") throw new Error(`${path} must be a string`);
  return value;
}

function requireInteger(value: unknown, path: string): number {
  if (!Number.isInteger(value)) throw new Error(`${path} must be an integer`);
  return value as number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
