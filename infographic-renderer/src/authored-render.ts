import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const moduleDir = dirname(fileURLToPath(import.meta.url));
const rendererRoot = resolve(moduleDir, "../..");
const appRoot = resolve(rendererRoot, "..");

interface AuthoredCanvas {
  width: number;
  height: number;
}

interface AuthoredInput {
  canvas: AuthoredCanvas;
  html: string;
  css: string;
  metadata?: Record<string, unknown>;
}

export async function renderAuthoredFromFile(inputPath: string, outputPath: string): Promise<void> {
  const raw = await readFile(inputPath, "utf8");
  const input = validateAuthoredInput(JSON.parse(raw));
  await renderAuthored(input, outputPath);
  console.log(`Validated authored infographic: ${inputPath}`);
  console.log(`Rendering at ${input.canvas.width}x${input.canvas.height}`);
  console.log(`Written: ${outputPath}`);
}

export function validateAuthoredInput(value: unknown): AuthoredInput {
  if (!isRecord(value)) throw new Error("input must be an object");
  if (!isRecord(value.canvas)) throw new Error("canvas must be an object");

  const width = requireInteger(value.canvas.width, "canvas.width");
  const height = requireInteger(value.canvas.height, "canvas.height");
  if (width !== 1280 || height !== 720) {
    throw new Error("canvas must be exactly 1280x720");
  }

  const html = requireString(value.html, "html", 120_000);
  const css = requireString(value.css, "css", 120_000);
  validateSafeHtml(html);
  validateSafeCss(css);

  return {
    canvas: { width, height },
    html,
    css,
    metadata: isRecord(value.metadata) ? value.metadata : undefined
  };
}

async function renderAuthored(input: AuthoredInput, outputPath: string): Promise<void> {
  const htmlPath = resolve(rendererRoot, "output/authored-render.html");
  await mkdir(dirname(htmlPath), { recursive: true });
  await mkdir(dirname(outputPath), { recursive: true });

  const documentHtml = await authoredDocument(input);
  await writeFile(htmlPath, documentHtml, "utf8");

  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({
      viewport: { width: input.canvas.width, height: input.canvas.height },
      deviceScaleFactor: 1,
      javaScriptEnabled: false
    });
    const page = await context.newPage();
    await page.route("**/*", route => route.abort());
    await page.setContent(documentHtml, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.fonts.ready);
    await page.locator("#infographic").screenshot({
      path: outputPath,
      type: "png"
    });
    await context.close();
  } finally {
    await browser.close();
  }
}

async function authoredDocument(input: AuthoredInput): Promise<string> {
  const logoDataUri = await localImageDataUri(resolve(appRoot, "frontend/assets/muddys-logo.png"));
  const html = input.html.replaceAll("{{MUDDYS_LOGO_DATA_URI}}", logoDataUri);
  const css = input.css.replaceAll("{{MUDDYS_LOGO_DATA_URI}}", logoDataUri);

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=1280,height=720,initial-scale=1">
  <style>
    * { box-sizing: border-box; }
    html, body {
      width: 1280px;
      height: 720px;
      margin: 0;
      overflow: hidden;
      background: #000;
    }
    #infographic {
      width: 1280px;
      height: 720px;
      overflow: hidden;
      position: relative;
      isolation: isolate;
    }
    ${css}
  </style>
</head>
<body>
  <div id="infographic">${html}</div>
</body>
</html>`;
}

async function localImageDataUri(path: string): Promise<string> {
  const buffer = await readFile(path);
  return `data:image/png;base64,${buffer.toString("base64")}`;
}

function validateSafeHtml(html: string): void {
  const blocked = [
    /<script\b/i,
    /<iframe\b/i,
    /<object\b/i,
    /<embed\b/i,
    /<link\b/i,
    /<meta\b/i,
    /\son[a-z]+\s*=/i,
    /javascript:/i,
    /https?:\/\//i,
    /src\s*=\s*["']\/\//i
  ];
  for (const pattern of blocked) {
    if (pattern.test(html)) {
      throw new Error(`html contains blocked content: ${pattern}`);
    }
  }
}

function validateSafeCss(css: string): void {
  const blocked = [
    /@import/i,
    /javascript:/i,
    /https?:\/\//i,
    /url\(\s*["']?\/\//i,
    /url\(\s*["']?file:/i,
    /expression\s*\(/i
  ];
  for (const pattern of blocked) {
    if (pattern.test(css)) {
      throw new Error(`css contains blocked content: ${pattern}`);
    }
  }
}

function requireString(value: unknown, label: string, maxLength: number): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} must be a non-empty string`);
  }
  if (value.length > maxLength) {
    throw new Error(`${label} must be ${maxLength} characters or fewer`);
  }
  return value;
}

function requireInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new Error(`${label} must be an integer`);
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
