import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptDir, "..");
const nextBin = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
const serverDir = path.join(frontendDir, ".next", "server");
const sourceDir = path.join(serverDir, "vendor-chunks");
const targetParentDir = path.join(serverDir, "chunks");
const targetDir = path.join(targetParentDir, "vendor-chunks");

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function ensureVendorChunkAlias() {
  if (!(await pathExists(sourceDir))) {
    return;
  }

  await fs.mkdir(targetParentDir, { recursive: true });

  if (await pathExists(targetDir)) {
    return;
  }

  try {
    await fs.symlink(sourceDir, targetDir, "dir");
    return;
  } catch {
    await fs.mkdir(targetDir, { recursive: true });
  }

  const entries = await fs.readdir(sourceDir);
  await Promise.all(
    entries.map(async (entry) => {
      const from = path.join(sourceDir, entry);
      const to = path.join(targetDir, entry);
      if (!(await pathExists(to))) {
        await fs.copyFile(from, to);
      }
    }),
  );
}

const child = spawn(process.execPath, [nextBin, "dev"], {
  cwd: frontendDir,
  stdio: "inherit",
  env: process.env,
});

const interval = setInterval(() => {
  ensureVendorChunkAlias().catch(() => {});
}, 500);

child.on("exit", (code, signal) => {
  clearInterval(interval);
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});

for (const event of ["SIGINT", "SIGTERM"]) {
  process.on(event, () => {
    clearInterval(interval);
    child.kill(event);
  });
}
