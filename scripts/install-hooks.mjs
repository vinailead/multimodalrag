import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const gitHooksDir = path.join(repoRoot, ".git", "hooks");

if (fs.existsSync(gitHooksDir)) {
  const preCommitPath = path.join(gitHooksDir, "pre-commit");
  const hookScript = `#!/usr/bin/env sh
node scripts/pre-commit.mjs
`;
  fs.writeFileSync(preCommitPath, hookScript, { encoding: "utf8", mode: 0o755 });
  try {
    fs.chmodSync(preCommitPath, 0o755);
  } catch {
    // Windows chmod is a no-op; safe to ignore
  }
  console.log("[ADLC] Installed git pre-commit hook at .git/hooks/pre-commit");
} else {
  console.log("[ADLC] .git/hooks not found, skipping pre-commit hook installation.");
}
