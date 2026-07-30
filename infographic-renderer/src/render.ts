import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { renderHtml } from "./template/chart.js";
import { blankInput, validateInput } from "./validate.js";

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, "../..");

export async function renderFromFile(inputPath: string, outputPath: string): Promise<void> {
  const raw = await readFile(inputPath, "utf8");
  const data = validateInput(JSON.parse(raw));
  await renderData(data, outputPath);
  console.log(`Validated: ${inputPath}`);
  console.log(`Loaded ${data.chart.length} chart entries`);
  console.log(`Loaded ${data.chartTalk.length} Chart Talk items`);
  console.log("Rendering at 1280x720");
  console.log(`Written: ${outputPath}`);
}

export async function renderBlank(outputPath: string): Promise<void> {
  await renderData(blankInput(), outputPath);
  console.log("Rendering blank template at 1280x720");
  console.log(`Written: ${outputPath}`);
}

async function renderData(data: ReturnType<typeof validateInput>, outputPath: string): Promise<void> {
  const htmlPath = resolve(repoRoot, "output/render.html");
  const cssPath = resolve(repoRoot, "output/chart.css");
  const sourceCssPath = resolve(repoRoot, "src/template/chart.css");
  await mkdir(dirname(htmlPath), { recursive: true });
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(htmlPath, renderHtml(data), "utf8");
  await writeFile(cssPath, await readFile(sourceCssPath, "utf8"), "utf8");

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 720 },
      deviceScaleFactor: 1
    });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`file://${htmlPath}`, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    const locator = page.locator("#infographic");
    await locator.screenshot({
      path: outputPath,
      type: "png"
    });
  } finally {
    await browser.close();
  }
}
