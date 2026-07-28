#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="/private/tmp/smart-meal-ai-one-deploy"

cd "$ROOT_DIR"

"$ROOT_DIR/scripts/build_vercel_combined.sh"

rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR/.vercel"
cp -R "$ROOT_DIR/.vercel/output" "$DEPLOY_DIR/.vercel/output"
cp "$ROOT_DIR/.vercel/project.json" "$DEPLOY_DIR/.vercel/project.json"
mkdir -p "$DEPLOY_DIR/.vercel/output/functions/api"
cp -R "$ROOT_DIR/.vercel/output/functions/api/index.py.func" "$DEPLOY_DIR/.vercel/output/functions/api/index.py.func"

node - "$ROOT_DIR" "$DEPLOY_DIR" <<'NODE'
const fs = require("fs");
const path = require("path");

const root = process.argv[2];
const deployDir = process.argv[3];
const apiConfigPath = path.join(root, ".vercel/output/functions/api/index.py.func/.vc-config.json");
const apiConfig = JSON.parse(fs.readFileSync(apiConfigPath, "utf8"));

for (const [deployPath, sourcePath] of Object.entries(apiConfig.filePathMap || {})) {
  const source = path.join(root, sourcePath);
  if (!fs.existsSync(source) || fs.statSync(source).isDirectory()) continue;
  for (const targetPath of new Set([sourcePath, deployPath])) {
    const target = path.join(deployDir, targetPath);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(source, target);
  }
}
NODE

npx vercel@56.5.0 deploy --prebuilt --prod --yes --cwd "$DEPLOY_DIR"
