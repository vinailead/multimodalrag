import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");

const backendPort = process.env.MMRAG_API_PORT || "8000";
const uiPort = process.env.MMRAG_UI_PORT || "5173";

console.log(`[ADLC DEV] Starting FastAPI backend on http://127.0.0.1:${backendPort} ...`);
const apiProc = spawn(
  "uv",
  [
    "run",
    "uvicorn",
    "insurance_mmrag.api.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    backendPort,
  ],
  {
    cwd: repoRoot,
    stdio: "inherit",
    shell: process.platform === "win32",
  },
);

const npxCmd = process.platform === "win32" ? "npx.cmd" : "npx";
console.log(`[ADLC DEV] Starting Google Material 3 Web UI on http://127.0.0.1:${uiPort} ...`);
const uiProc = spawn(npxCmd, ["vite", "--host", "127.0.0.1", "--port", uiPort], {
  cwd: repoRoot,
  stdio: "inherit",
  shell: process.platform === "win32",
});

function shutdown() {
  apiProc.kill("SIGTERM");
  uiProc.kill("SIGTERM");
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
