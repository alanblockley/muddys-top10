import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { validateAuthoredInput } from "../src/authored-render.js";

const example = JSON.parse(readFileSync(resolve("examples/authored-infographic.example.json"), "utf8"));

const valid = validateAuthoredInput(example);
assert.equal(valid.canvas.width, 1280);
assert.equal(valid.canvas.height, 720);
assert.match(valid.html, /poster/);
assert.match(valid.css, /\.poster/);

const badSize = structuredClone(example);
badSize.canvas.width = 1024;
assert.throws(() => validateAuthoredInput(badSize), /1280x720/);

const scriptHtml = structuredClone(example);
scriptHtml.html = '<main><script>alert("no")</script></main>';
assert.throws(() => validateAuthoredInput(scriptHtml), /blocked content/);

const eventHandlerHtml = structuredClone(example);
eventHandlerHtml.html = '<main onclick="alert()">Bad</main>';
assert.throws(() => validateAuthoredInput(eventHandlerHtml), /blocked content/);

const remoteCss = structuredClone(example);
remoteCss.css = ".poster{background:url(https://example.com/x.png)}";
assert.throws(() => validateAuthoredInput(remoteCss), /blocked content/);

const remoteHtml = structuredClone(example);
remoteHtml.html = '<img src="https://example.com/x.png">';
assert.throws(() => validateAuthoredInput(remoteHtml), /blocked content/);

console.log("authored render tests passed");
