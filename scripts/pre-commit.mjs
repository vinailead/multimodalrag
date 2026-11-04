import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");

const args = new Set(process.argv.slice(2));
const isDryRun = args.has("--dry-run");

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

function runStep(label, command, cmdArgs) {
  console.log(`\n=== [PRE-COMMIT] ${label}: ${command} ${cmdArgs.join(" ")} ===`);
  if (isDryRun) {
    return;
  }
  const result = spawnSync(command, cmdArgs, {
    cwd: repoRoot,
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.status !== 0) {
    console.error(`\n[PRE-COMMIT FAILED] Step failed: ${label}`);
    process.exit(result.status ?? 1);
  }
}

runStep("Python Ruff Lint", uvCmd, ["run", "ruff", "check", "src", "tests", "scripts"]);
runStep("Python Ruff Format Check", uvCmd, [
  "run",
  "ruff",
  "format",
  "--check",
  "src",
  "tests",
  "scripts",
]);
runStep("Python Pyright Typecheck", uvCmd, ["run", "pyright"]);
runStep("Python Bandit Security Scan", uvCmd, [
  "run",
  "bandit",
  "-c",
  "pyproject.toml",
  "-r",
  "src",
  "scripts",
]);
runStep("Python Pytest + Coverage (>=80%)", uvCmd, [
  "run",
  "pytest",
  "--cov=src/insurance_mmrag",
  "--cov-fail-under=80",
]);

const uiSrcDir = path.join(repoRoot, "ui", "web", "src");
if (fs.existsSync(uiSrcDir)) {
  const npxCmd = process.platform === "win32" ? "npx.cmd" : "npx";
  runStep("TypeScript ESLint", npxCmd, ["eslint", "ui/web/src", "e2e"]);
  runStep("TypeScript Prettier Check", npxCmd, [
    "prettier",
    "--check",
    "ui/web/src/**/*.{ts,css}",
    "e2e/**/*.ts",
  ]);
  runStep("TypeScript Compiler Check", npxCmd, ["tsc", "--noEmit"]);
  runStep("TypeScript Vitest Unit Tests (>=80% cov)", npxCmd, [
    "vitest",
    "run",
    "--coverage",
  ]);
}

console.log("\n[PRE-COMMIT PASSED] All quality gates succeeded.");
