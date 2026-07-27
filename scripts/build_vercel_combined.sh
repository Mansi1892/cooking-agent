#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_API_FUNC="${TMPDIR:-/tmp}/smart-meal-ai-api-func"

cd "$ROOT_DIR"

rm -rf "$TMP_API_FUNC"
mkdir -p "$TMP_API_FUNC"

npx vercel build --prod
cp -R "$ROOT_DIR/.vercel/output/functions/api/index.py.func" "$TMP_API_FUNC/index.py.func"

cd "$ROOT_DIR/frontend"
npx vercel build --prod

cd "$ROOT_DIR"
rm -rf "$ROOT_DIR/.vercel/output"
cp -R "$ROOT_DIR/frontend/.vercel/output" "$ROOT_DIR/.vercel/output"
mkdir -p "$ROOT_DIR/.vercel/output/functions/api"
cp -R "$TMP_API_FUNC/index.py.func" "$ROOT_DIR/.vercel/output/functions/api/index.py.func"

node - <<'NODE'
const fs = require("fs");
const path = ".vercel/output/config.json";
const config = JSON.parse(fs.readFileSync(path, "utf8"));
const routes = config.routes || [];
config.routes = [
  { src: "^/api(?:/(.*))?$", dest: "/api/index.py" },
  ...routes.filter((route) => !(route.src && String(route.src).includes("/api"))),
];
fs.writeFileSync(path, JSON.stringify(config, null, 2) + "\n");
NODE

echo "Combined Vercel output ready at .vercel/output"
