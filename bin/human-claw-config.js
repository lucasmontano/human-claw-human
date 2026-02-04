#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const DEFAULT_API = "http://72.62.53.103:8090";

function parseArgs(argv) {
  const out = { workdir: process.cwd(), api: DEFAULT_API };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--workdir") out.workdir = argv[++i];
    else if (a === "--api") out.api = argv[++i];
    else if (a === "-h" || a === "--help") out.help = true;
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(`human-claw-config\n\nUsage:\n  npx github:lucasmontano/human-claw-human#main -- human-claw-config --workdir . --api http://72.62.53.103:8090\n\nNotes:\n- Writes ./skills/human-claw/config.json\n`);
    process.exit(0);
  }

  const skillDir = path.join(args.workdir, "skills", "human-claw");
  fs.mkdirSync(skillDir, { recursive: true });
  const cfgPath = path.join(skillDir, "config.json");
  const cfg = { marketplaceBaseUrl: args.api };
  fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2) + "\n", "utf8");
  console.log(`Wrote ${cfgPath}`);
}

main();
