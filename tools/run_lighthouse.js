const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const url = process.argv[2] || "http://127.0.0.1:8000/spa/";
const dataDir = path.resolve(__dirname, "..", "data");

const runId = new Date().toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[:\-]/g, "");
const outArg = process.argv[3];
const basePath = (() => {
  if (outArg) {
    const resolved = path.resolve(outArg);
    const ext = path.extname(resolved).toLowerCase();
    if (ext === ".json" || ext === ".html") return resolved.slice(0, -ext.length);
    return resolved;
  }
  return path.join(dataDir, `lighthouse.performance.${runId}`);
})();

const profileDir = path.join(dataDir, "lh-profile", runId);
fs.mkdirSync(dataDir, { recursive: true });
fs.mkdirSync(profileDir, { recursive: true });
const chromeUserDataDir = profileDir.replaceAll("\\", "/");
const chromeFlags =
  `--headless=new --user-data-dir="${chromeUserDataDir}" ` +
  "--disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling " +
  "--disable-features=CalculateNativeWinOcclusion " +
  "--no-first-run --no-default-browser-check";

const args = [
  "-y",
  "lighthouse",
  url,
  "--enable-error-reporting=false",
  "--only-categories=performance",
  "--output=json",
  "--output=html",
  `--output-path=${basePath}`,
  `--chrome-flags=${chromeFlags}`,
  "--preset=desktop",
  "--throttling-method=simulate",
  "--quiet",
];

const npxBin = process.platform === "win32" ? "npx.cmd" : "npx";
const r = spawnSync(npxBin, args, { encoding: "utf8", shell: process.platform === "win32" });
if (r.error) {
  process.stderr.write(String(r.error) + "\n");
  process.exit(1);
}
if (r.stdout) process.stdout.write(r.stdout);
if (r.stderr) process.stderr.write(r.stderr);
if (typeof r.status === "number" && r.status !== 0) process.exit(r.status);

const jsonCandidates = [`${basePath}.report.json`, `${basePath}.json`];
const htmlCandidates = [`${basePath}.report.html`, `${basePath}.html`];
const jsonPath = jsonCandidates.find((p) => fs.existsSync(p));
const htmlPath = htmlCandidates.find((p) => fs.existsSync(p));

if (!jsonPath) {
  process.stderr.write(`Lighthouse 输出未找到（期望：${jsonCandidates.join(", ")}）\n`);
  process.exit(1);
}

const latestJson = path.join(dataDir, "lighthouse.performance.json");
fs.copyFileSync(jsonPath, latestJson);
if (htmlPath) {
  const latestHtml = path.join(dataDir, "lighthouse.performance.html");
  fs.copyFileSync(htmlPath, latestHtml);
}

const report = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
const audits = report.audits || {};
const pick = (id) => {
  const a = audits[id];
  if (!a) return null;
  return { numericValue: a.numericValue, displayValue: a.displayValue };
};

const summary = {
  url,
  fetchTime: report.fetchTime,
  lighthouseVersion: report.lighthouseVersion,
  performanceScore: Math.round(((report.categories?.performance?.score ?? 0) * 100 + Number.EPSILON) * 10) / 10,
  metrics: {
    fcp: pick("first-contentful-paint"),
    lcp: pick("largest-contentful-paint"),
    speedIndex: pick("speed-index"),
    tti: pick("interactive"),
    tbt: pick("total-blocking-time"),
    cls: pick("cumulative-layout-shift"),
  },
  paths: {
    json: jsonPath,
    html: htmlPath || null,
    latestJson,
    latestHtml: htmlPath ? path.join(dataDir, "lighthouse.performance.html") : null,
  },
};

const summaryPath = `${basePath}.summary.json`;
const latestSummary = path.join(dataDir, "lighthouse.performance.summary.json");
fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");
fs.copyFileSync(summaryPath, latestSummary);
process.stdout.write(`${summary.performanceScore}\n`);

