#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import https from "node:https";

function parseArgs(argv) {
  const out = { repo: null, ref: "main", workdir: process.cwd() };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--repo") out.repo = argv[++i];
    else if (a === "--ref") out.ref = argv[++i];
    else if (a === "--workdir") out.workdir = argv[++i];
  }
  return out;
}

function fetchText(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, { headers: { "User-Agent": "clawmarket-installer" } }, (res) => {
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          res.resume();
          return;
        }
        let data = "";
        res.setEncoding("utf8");
        res.on("data", (c) => (data += c));
        res.on("end", () => resolve(data));
      })
      .on("error", reject);
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args.repo) {
    console.error("Usage: clawmarket-install --repo <owner/repo> [--ref main] [--workdir <dir>]");
    process.exit(1);
  }

  // Where OpenClaw loads workspace skills from:
  const skillDir = path.join(args.workdir, "skills", "human-claw");
  const refsDir = path.join(skillDir, "references");

  fs.mkdirSync(refsDir, { recursive: true });

  const base = `https://raw.githubusercontent.com/${args.repo}/${args.ref}/skills/public/human-claw`;
  const skillMdUrl = `${base}/SKILL.md`;
  const apiMdUrl = `${base}/references/api.md`;

  const [skillMd, apiMd] = await Promise.all([
    fetchText(skillMdUrl),
    fetchText(apiMdUrl)
  ]);

  fs.writeFileSync(path.join(skillDir, "SKILL.md"), skillMd, "utf8");
  fs.writeFileSync(path.join(refsDir, "api.md"), apiMd, "utf8");

  console.log(`Installed Human Claw skill to: ${skillDir}`);
  console.log("Next: restart OpenClaw / start a new session so it loads the new skill.");
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
