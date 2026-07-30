import type { ChartEntry, MovementType } from "../types.js";

export interface MovementDisplay {
  type: MovementType;
  symbol: string;
  label: string;
  className: string;
}

export function movementDisplay(entry: ChartEntry): MovementDisplay {
  const type = entry.movement.type;
  const places = entry.movement.places ?? 0;

  if (type === "up") {
    return {
      type,
      symbol: "up",
      label: `UP ${places}`,
      className: "movement-up"
    };
  }

  if (type === "down") {
    return {
      type,
      symbol: "down",
      label: `DOWN ${places}`,
      className: "movement-down"
    };
  }

  if (type === "same") {
    return {
      type,
      symbol: "same",
      label: "NON-MOVER",
      className: "movement-same"
    };
  }

  if (type === "reentry") {
    return {
      type,
      symbol: "reentry",
      label: "RE-ENTRY",
      className: "movement-reentry"
    };
  }

  return {
    type,
    symbol: "new",
    label: "NEW",
    className: "movement-new"
  };
}

export function movementSvg(symbol: MovementDisplay["symbol"]): string {
  if (symbol === "up") {
    return `<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 4 35 21h-9v15H14V21H5Z" /></svg>`;
  }
  if (symbol === "down") {
    return `<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 36 5 19h9V4h12v15h9Z" /></svg>`;
  }
  if (symbol === "same") {
    return `<svg viewBox="0 0 40 40" aria-hidden="true"><rect x="7" y="17" width="26" height="6" rx="3" /></svg>`;
  }
  if (symbol === "reentry") {
    return `<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M21 6a14 14 0 1 1-11 5.3l-4.7.1 7-7 7 7-5.1-.1A9 9 0 1 0 21 11Z" /></svg>`;
  }
  return `<svg viewBox="0 0 40 40" aria-hidden="true"><path d="m20 3 5 11 12 1-9 8 3 12-11-6-11 6 3-12-9-8 12-1Z" /></svg>`;
}

