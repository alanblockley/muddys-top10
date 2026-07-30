export type MovementType = "new" | "up" | "down" | "same" | "reentry";
export type LayoutVariant = "standard" | "feature-climber" | "feature-number-one" | "feature-long-run";
export type ChartTalkEmphasis = "normal" | "feature";
export type ChartTalkIcon = "trophy" | "rocket" | "star" | "note" | "music" | "weeks" | "climber";

export interface LayoutIntent {
  variant: LayoutVariant;
  featured_story?: string;
}

export interface ChartEntry {
  position: number;
  artist: string;
  title: string;
  plays: number;
  movement: {
    type: MovementType;
    places?: number;
  };
}

export interface ChartTalkItem {
  slot: number;
  kind: string;
  icon?: ChartTalkIcon;
  emphasis?: ChartTalkEmphasis;
  heading: string;
  body: string;
  short_body?: string;
  metrics?: Record<string, string | number>;
}

export interface ChartBadge {
  position: number;
  label: string;
  tone?: "new" | "up" | "down" | "feature";
}

export interface RenderInput {
  layout?: Partial<LayoutIntent>;
  week: {
    start: string;
    end: string;
    display: string;
  };
  chart: ChartEntry[];
  chartTalk: ChartTalkItem[];
  chartBadges?: ChartBadge[];
  stats: {
    newEntries: number;
    climbers: number;
    fallers: number;
    nonMovers: number;
  };
  facts: string[];
  numbers: {
    totalPlaysThisWeek: number;
    totalPlaysLastWeek: number;
    percentageChange: number;
    weeksSinceLaunch: number;
    differentArtists: number;
  };
  show?: {
    time?: string;
    day?: string;
    presenters?: string;
    presenterTagline?: string;
    venueName?: string;
    venueTagline?: string;
    compiledFrom?: string;
  };
}

export interface NormalizedRenderInput extends RenderInput {
  layout: LayoutIntent;
  show: Required<NonNullable<RenderInput["show"]>>;
  chartBadges: ChartBadge[];
}
