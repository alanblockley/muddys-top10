const { GetObjectCommand, PutObjectCommand } = require("@aws-sdk/client-s3");
const { S3Client } = require("@aws-sdk/client-s3");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { renderToPng } = require("./chart-poster");

const s3 = new S3Client({});
const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 720;

exports.lambda_handler = async (event) => {
  const bucket = process.env.CAMPAIGN_ASSETS_BUCKET;
  if (!bucket) {
    throw new Error("CAMPAIGN_ASSETS_BUCKET is not configured");
  }

  // Route: AntV chart data path (new) vs legacy HTML/CSS path
  if (event.chart_data) {
    return renderChartPoster(event, bucket);
  }
  return renderLegacyHtmlCss(event, bucket);
};

/**
 * New path: Render chart data via AntV Infographic SSR → PNG
 */
async function renderChartPoster(event, bucket) {
  const chartData = event.chart_data;
  const weekId = safeToken(chartData.week_id || event.week_id || "unknown", "week");

  // Render to PNG
  const result = await renderToPng(chartData);
  if (result.width !== CANVAS_WIDTH || result.height !== CANVAS_HEIGHT) {
    console.warn(`Output dimensions ${result.width}x${result.height}, expected ${CANVAS_WIDTH}x${CANVAS_HEIGHT}`);
  }

  // Upload to S3
  const generatedAt = new Date().toISOString();
  const outputPrefix = safePrefix(event.output_prefix || `campaigns/${weekId}`);
  const filenamePrefix = safeToken(event.filename_prefix || "infographic", "infographic");
  const key = `${outputPrefix}/${filenamePrefix}-${generatedAt.replace(/[:.]/g, "-")}.png`;

  await s3.send(new PutObjectCommand({
    Bucket: bucket,
    Key: key,
    Body: result.png,
    ContentType: "image/png",
    CacheControl: "private, max-age=31536000",
    Metadata: {
      week_id: weekId,
      renderer: "antv-infographic",
      svg_length: String(result.svgLength)
    }
  }));

  return {
    ok: true,
    infographic_png: {
      bucket,
      key,
      content_type: "image/png",
      width: result.width,
      height: result.height,
      size_bytes: result.png.length,
      generated_at: generatedAt,
      renderer: "antv-infographic"
    }
  };
}

/**
 * Legacy path: Render HTML/CSS via Playwright (kept for backward compat)
 */
async function renderLegacyHtmlCss(event, bucket) {
  // Lazy-load Playwright only when needed (heavy deps)
  const chromium = require("@sparticuz/chromium");
  const { chromium: playwrightChromium } = require("playwright-core");

  const asset = validateAsset(event.infographic_asset || event.asset);
  const weekId = requireString(event.week_id || asset.metadata?.week_id, "week_id", 32);
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
    await page.route("**/*", route => route.abort());
    await page.setContent(documentHtml, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.fonts.ready);
    const png = await page.locator("#infographic").screenshot({ type: "png" });
    await context.close();

    const generatedAt = new Date().toISOString();
    const safeWeekId = safeToken(weekId, "week");
    const outputPrefix = safePrefix(event.output_prefix || `campaigns/${safeWeekId}`);
    const filenamePrefix = safeToken(event.filename_prefix || "infographic", "infographic");
    const key = `${outputPrefix}/${filenamePrefix}-${generatedAt.replace(/[:.]/g, "-")}.png`;

    await s3.send(new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: png,
      ContentType: "image/png",
      CacheControl: "private, max-age=31536000",
      Metadata: {
        week_id: weekId,
        source_snapshot_key: String(asset.metadata?.source_snapshot_key || "")
      }
    }));

    return {
      ok: true,
      infographic_png: {
        bucket,
        key,
        content_type: "image/png",
        width: CANVAS_WIDTH,
        height: CANVAS_HEIGHT,
        size_bytes: png.length,
        generated_at: generatedAt,
        source_snapshot_key: asset.metadata?.source_snapshot_key || null
      }
    };
  } finally {
    await browser.close();
  }
};

function validateAsset(value) {
  if (!isRecord(value)) throw new Error("infographic_asset must be an object");
  if (!isRecord(value.canvas)) throw new Error("infographic_asset.canvas must be an object");

  const width = requireInteger(value.canvas.width, "canvas.width");
  const height = requireInteger(value.canvas.height, "canvas.height");
  if (width !== CANVAS_WIDTH || height !== CANVAS_HEIGHT) {
    throw new Error("infographic canvas must be exactly 1280x720");
  }

  const html = requireString(value.html, "html", 120000);
  const css = requireString(value.css, "css", 120000);
  validateSafeHtml(html);
  validateSafeCss(css);

  return {
    canvas: { width, height },
    html,
    css,
    metadata: isRecord(value.metadata) ? value.metadata : {}
  };
}

async function buildDocument(asset, bucket) {
  const logoDataUri = await campaignLogoDataUri(asset, bucket);
  const html = asset.html.replaceAll("{{MUDDYS_LOGO_DATA_URI}}", logoDataUri);
  const css = asset.css.replaceAll("{{MUDDYS_LOGO_DATA_URI}}", logoDataUri);

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

async function campaignLogoDataUri(asset, bucket) {
  if (process.env.MUDDYS_LOGO_DATA_URI) {
    return process.env.MUDDYS_LOGO_DATA_URI;
  }
  const brand = asset.metadata?.brand_config_snapshot || {};
  const key = brand.logo_s3_key;
  if (!key) {
    return localLogoDataUri();
  }
  try {
    const response = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
    const body = await streamToBuffer(response.Body);
    const contentType = response.ContentType || brand.logo_content_type || "image/png";
    return `data:${contentType};base64,${body.toString("base64")}`;
  } catch (error) {
    console.warn(`Unable to load campaign logo ${key}; using bundled logo`, error);
    return localLogoDataUri();
  }
}

async function streamToBuffer(stream) {
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

function localLogoDataUri() {
  const logo = readFileSync(join(__dirname, "assets", "muddys-logo.png"));
  return `data:image/png;base64,${logo.toString("base64")}`;
}

function validateSafeHtml(html) {
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

function validateSafeCss(css) {
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

function requireString(value, label, maxLength) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} must be a non-empty string`);
  }
  if (value.length > maxLength) {
    throw new Error(`${label} must be ${maxLength} characters or fewer`);
  }
  return value;
}

function requireInteger(value, label) {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new Error(`${label} must be an integer`);
  }
  return value;
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeToken(value, fallback) {
  const token = String(value || "").replace(/[^A-Za-z0-9_-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return token || fallback;
}

function safePrefix(value) {
  return String(value || "")
    .split("/")
    .map((part) => safeToken(part, "asset"))
    .filter(Boolean)
    .join("/")
    .slice(0, 700) || "campaigns/asset";
}
