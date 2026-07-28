#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_API_FUNC="${TMPDIR:-/tmp}/smart-meal-ai-api-func"

cd "$ROOT_DIR"

rm -rf "$TMP_API_FUNC"
mkdir -p "$TMP_API_FUNC"
npx vercel build --prod --local-config "$ROOT_DIR/scripts/vercel.api.json"
cp -R "$ROOT_DIR/.vercel/output/functions/api/index.py.func" "$TMP_API_FUNC/index.py.func"

cd "$ROOT_DIR/frontend"
npx vercel pull --yes --environment production --project smart-meal-ai-one
npx vercel build --prod

cd "$ROOT_DIR"
rm -rf "$ROOT_DIR/.vercel/output"
cp -R "$ROOT_DIR/frontend/.vercel/output" "$ROOT_DIR/.vercel/output"
mkdir -p "$ROOT_DIR/.vercel/output/functions/api"
cp -R "$TMP_API_FUNC/index.py.func" "$ROOT_DIR/.vercel/output/functions/api/index.py.func"

node - <<'NODE'
const fs = require("fs");
const configPath = ".vercel/output/config.json";
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const routes = config.routes || [];
config.routes = [
  { src: "^/api(?:/(.*))?$", dest: "/api/index.py" },
  ...routes.filter((route) => !(route.src && String(route.src).includes("/api"))),
];
fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");

const apiConfigPath = ".vercel/output/functions/api/index.py.func/.vc-config.json";
const apiConfig = JSON.parse(fs.readFileSync(apiConfigPath, "utf8"));
const backendFiles = new Set([
  ".python-version",
  ".vercelignore",
  "pyproject.toml",
  "requirements.txt",
  "uv.lock",
]);
apiConfig.filePathMap = Object.fromEntries(
  Object.entries(apiConfig.filePathMap || {}).filter(([source]) => {
    const normalized = source.replace(/\\/g, "/");
    const name = normalized.split("/").pop() || "";
    if (
      name === ".env" ||
      name.startsWith(".env.") ||
      normalized.includes("/.env") ||
      normalized.includes("/.vercel/.env") ||
      normalized.startsWith(".git/") ||
      normalized.startsWith(".pytest_cache/") ||
      normalized.startsWith(".vercel/") ||
      normalized.startsWith("frontend/") ||
      normalized.startsWith("node_modules/")
    ) {
      return false;
    }
    return (
      backendFiles.has(normalized) ||
      (/^[^/]+\.py$/.test(normalized) && normalized !== "test_flow.py") ||
      normalized.startsWith("api/") ||
      normalized.startsWith("data/") ||
      normalized.startsWith("_vendor/") ||
      normalized.startsWith("_uv/")
    );
  })
);
apiConfig.filePathMap["_uv/uv"] = "_uv/uv";
fs.writeFileSync(apiConfigPath, JSON.stringify(apiConfig, null, 2) + "\n");
NODE

echo "Combined Vercel output ready at .vercel/output"
