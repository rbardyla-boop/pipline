/**
 * Dagger pipeline configuration for TruthLens container builds.
 * Reference: dagger/container-use
 *
 * Provides reproducible, cached container builds for CI and production.
 * Ensures the pinned base image digest is verified on every build.
 *
 * Usage (requires Dagger CLI):
 *   dagger run tsx agent_sandbox/container/dagger.ts
 *
 * Or via npm:
 *   cd agent_sandbox && npm run build-container
 */

import { connect, type Client } from "@dagger.io/dagger";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "../..");

const PINNED_BASE =
  "python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203";

async function build(client: Client): Promise<void> {
  const src = client.host().directory(PROJECT_ROOT, {
    exclude: [
      ".git",
      ".venv",
      "__pycache__",
      "node_modules",
      "agent_sandbox/node_modules",
      ".env",
      "*.pyc",
      "logs/runs",
      "logs/zeitgeist_cache.json",
    ],
  });

  const container = client
    .container()
    .from(PINNED_BASE)
    // Non-root user
    .withExec(["useradd", "-u", "65534", "-r", "-s", "/usr/sbin/nologin", "-d", "/app", "pipeline"])
    .withWorkdir("/app")
    // Install deps as root
    .withFile("requirements.txt", src.file("requirements.txt"))
    .withFile("requirements-security.txt", src.file("requirements-security.txt"))
    .withExec(["pip", "install", "--no-cache-dir", "-r", "requirements.txt"])
    .withExec(["pip", "install", "--no-cache-dir", "-r", "requirements-security.txt"])
    .withExec(["pip", "check"])
    .withExec(["pip", "cache", "purge"])
    // Copy application (exclude credentials)
    .withDirectory("/app", src, { owner: "pipeline" })
    // Scrub sensitive files
    .withExec(["sh", "-c", "rm -f .env .env.* *.key *.pem"])
    // Set non-root user
    .withUser("pipeline")
    // Environment: no credentials
    .withEnvVariable("ANTHROPIC_API_KEY", "")
    .withEnvVariable("TAVILY_API_KEY", "")
    .withEnvVariable("PYTHONDONTWRITEBYTECODE", "1")
    .withEnvVariable("PYTHONUNBUFFERED", "1")
    .withEnvVariable("PYTHONPATH", "/app");

  // Export image
  const imageRef = await container.export("/tmp/pipline-ci.tar");
  console.log(`[DAGGER] Image exported: ${imageRef}`);

  // Run trivy scan on exported image
  const trivyContainer = client
    .container()
    .from("aquasec/trivy:latest")
    .withMountedFile("/image.tar", client.host().file("/tmp/pipline-ci.tar"))
    .withExec([
      "trivy",
      "image",
      "--input", "/image.tar",
      "--severity", "CRITICAL,HIGH",
      "--exit-code", "1",
      "--format", "json",
    ]);

  const trivyOutput = await trivyContainer.stdout();
  console.log("[DAGGER] Trivy scan complete:", trivyOutput.slice(0, 200));
}

connect(
  async (client) => {
    await build(client);
  },
  { LogOutput: process.stderr }
).catch((err) => {
  console.error("[DAGGER] Build failed:", err);
  process.exit(1);
});
