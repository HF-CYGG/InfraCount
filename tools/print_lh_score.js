const fs = require("fs");

const jsonPath = process.argv[2] || "data/lh11.json";
const raw = fs.readFileSync(jsonPath, "utf8");
const report = JSON.parse(raw);
const score = Number(report?.categories?.performance?.score || 0) * 100;
const out = Math.round((score + Number.EPSILON) * 10) / 10;
process.stdout.write(String(out) + "\n");

