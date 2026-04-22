import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const rootDir = process.cwd();
const middlewarePath = path.join(rootDir, "middleware.ts");
const disabledMiddlewarePath = path.join(rootDir, "middleware.ts.static-disabled");

async function moveIfExists(fromPath, toPath) {
  try {
    await fs.rename(fromPath, toPath);
    return true;
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return false;
    }
    throw error;
  }
}

async function runBuild() {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.platform === "win32" ? "npx.cmd" : "npx",
      ["next", "build"],
      {
        cwd: rootDir,
        stdio: "inherit",
        env: {
          ...process.env,
          NEXT_PUBLIC_STATIC_EXPORT: "true",
        },
      },
    );

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`Static build failed with exit code ${code ?? "unknown"}`));
    });

    child.on("error", reject);
  });
}

let middlewareMoved = false;

try {
  middlewareMoved = await moveIfExists(middlewarePath, disabledMiddlewarePath);
  await runBuild();
} finally {
  if (middlewareMoved) {
    await moveIfExists(disabledMiddlewarePath, middlewarePath);
  }
}
