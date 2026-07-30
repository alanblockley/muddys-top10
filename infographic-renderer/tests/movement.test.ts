import assert from "node:assert/strict";
import { movementDisplay } from "../src/helpers/movement.js";
import type { ChartEntry } from "../src/types.js";

function entry(type: ChartEntry["movement"]["type"], places?: number): ChartEntry {
  return {
    position: 1,
    artist: "Artist",
    title: "Title",
    plays: 1,
    movement: { type, places }
  };
}

assert.equal(movementDisplay(entry("up", 5)).label, "UP 5");
assert.equal(movementDisplay(entry("down", 2)).label, "DOWN 2");
assert.equal(movementDisplay(entry("same", 0)).label, "NON-MOVER");
assert.equal(movementDisplay(entry("new")).label, "NEW");
assert.equal(movementDisplay(entry("reentry")).label, "RE-ENTRY");

console.log("movement tests passed");

