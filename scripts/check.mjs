import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");

const args = new Set(process.argv.slice(2));
const pyOnly = args.has("--py-only");
const tsOnly = args.has("--ts-only");
const e2eOnly = args.has("--e2e-only");
const runAll = !pyOnly && !tsOnly && !e2eOnly;

function runStep(label, command, cmdArgs) {
  console.log(`\n================================================================`);
  console.log(`[ADLC CHECK] ${label}`);
  console.log(`Command: ${command} ${cmdArgs.join(" ")}`);
  console.log(`================================================================`);
  const result = spawnSync(command, cmdArgs, {
    cwd: repoRoot,
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.status !== 0) {
    console.error(`\n[ADLC CHECK FAILED] ${label} exited with code ${result.status}`);
    process.exit(result.status ?? 1);
  }
}

function resolveBinary(name) {
  if (process.platform !== "win32") {
    const brewPath = path.join("/opt/homebrew/bin", name);
    if (fs.existsSync(brewPath)) {
      return brewPath;
    }
    const usrPath = path.join("/usr/local/bin", name);
    if (fs.existsSync(usrPath)) {
      return usrPath;
    }
  }
  return name;
}

const uvCmd = resolveBinary("uv");
const npxCmd = process.platform === "win32" ? "npx.cmd" : "npx";

if (runAll || pyOnly) {
  runStep("1. Python Lint (Ruff)", uvCmd, ["run", "ruff", "check", "src", "tests", "scripts"]);
  runStep("2. Python Format (Ruff)", uvCmd, [
    "run",
    "ruff",
    "format",
    "--check",
    "src",
    "tests",
    "scripts",
  ]);
  runStep("3. Python Static Types (Pyright)", uvCmd, ["run", "pyright"]);
  runStep("4. Python Security SAST (Bandit)", uvCmd, [
    "run",
    "bandit",
    "-c",
    "pyproject.toml",
    "-r",
    "src",
    "scripts",
  ]);
  runStep("5. Python Unit & API Tests (Pytest >= 80% coverage)", uvCmd, [
    "run",
    "pytest",
    "--cov=src/insurance_mmrag",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
  ]);
}

const uiSrcDir = path.join(repoRoot, "ui", "web", "src");
if ((runAll || tsOnly) && fs.existsSync(uiSrcDir)) {
  runStep("6. TypeScript Lint (ESLint)", npxCmd, ["eslint", "ui/web/src", "e2e"]);
  runStep("7. TypeScript Format (Prettier)", npxCmd, [
    "prettier",
    "--check",
    "ui/web/src/**/*.{ts,css}",
    "e2e/**/*.ts",
  ]);
  runStep("8. TypeScript Compiler (tsc --noEmit)", npxCmd, ["tsc", "--noEmit"]);
  runStep("9. TypeScript Unit Tests (Vitest >= 80% coverage)", npxCmd, [
    "vitest",
    "run",
    "--coverage",
  ]);
}

const e2eDir = path.join(repoRoot, "e2e");
if ((runAll || e2eOnly) && fs.existsSync(e2eDir)) {
  runStep("9b. Build Material 3 Web Bundle (Vite)", npxCmd, ["vite", "build"]);
  runStep("10. Browser End-to-End Tests (Playwright)", npxCmd, ["playwright", "test"]);
}

console.log("\n[ADLC CHECK SUCCESS] All configured quality gates passed 100%!");
