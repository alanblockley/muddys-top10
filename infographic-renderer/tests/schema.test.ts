import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { validateInput } from "../src/validate.js";

const example = JSON.parse(readFileSync(resolve("examples/chart.example.json"), "utf8"));

const valid = validateInput(example);
assert.equal(valid.chart.length, 10);
assert.equal(valid.chart[0].position, 1);
assert.equal(valid.layout.variant, "feature-climber");
assert.equal(valid.chartBadges.length, 2);
assert.equal(valid.chartTalk[5].emphasis, "feature");

const tooFew = structuredClone(example);
tooFew.chart = tooFew.chart.slice(0, 9);
assert.throws(() => validateInput(tooFew), /exactly 10/);

const duplicatePosition = structuredClone(example);
duplicatePosition.chart[1].position = 1;
assert.throws(() => validateInput(duplicatePosition), /duplicate 1/);

const invalidMovement = structuredClone(example);
invalidMovement.chart[0].movement.type = "sideways";
assert.throws(() => validateInput(invalidMovement), /movement\.type/);

const negativePlays = structuredClone(example);
negativePlays.chart[0].plays = -1;
assert.throws(() => validateInput(negativePlays), /plays must be non-negative/);

const invalidVariant = structuredClone(example);
invalidVariant.layout.variant = "chaos";
assert.throws(() => validateInput(invalidVariant), /layout\.variant/);

const invalidIcon = structuredClone(example);
invalidIcon.chartTalk[0].icon = "emoji-party";
assert.throws(() => validateInput(invalidIcon), /chartTalk\[0\]\.icon/);

const duplicateBadge = structuredClone(example);
duplicateBadge.chartBadges[1].position = duplicateBadge.chartBadges[0].position;
assert.throws(() => validateInput(duplicateBadge), /chartBadges positions must be unique/);

console.log("schema tests passed");
