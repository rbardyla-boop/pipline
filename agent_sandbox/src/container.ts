/**
 * Container lifecycle management for the Epistemic Sandbox Runtime.
 *
 * Wraps `docker run` with the hardened security profile:
 * - Read-only root filesystem
 * - seccomp profile from agent_sandbox/container/seccomp.json
 * - No capabilities
 * - Non-root user (65534)
 * - Internal network only (gateway-reachable)
 * - Resource limits enforced
 *
 * Also integrates with dagger/container-use when DAGGER_MODE=true.
 */

import { execSync, spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SECCOMP_PATH = path.resolve(__dirname, "../container/seccomp.json");
const PROJECT_ROOT = path.resolve(__dirname, "../..");

export interface ContainerConfig {
  image: string;
  gatewayUrl: string;
  domain: string;
  seedsPath: string;
  maxMemoryMB: number;
  maxCpuCores: number;
  timeoutSeconds: number;
  logsDir: string;
}

export interface ContainerResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  durationMs: number;
  timedOut: boolean;
}

const DEFAULT_CONFIG: Omit<ContainerConfig, "domain" | "seedsPath"> = {
  image: "pipline:latest",
  gatewayUrl: process.env["GATEWAY_URL"] ?? "http://gateway:8080",
  maxMemoryMB: 1024,
  maxCpuCores: 2,
  timeoutSeconds: 600,
  logsDir: path.join(PROJECT_ROOT, "logs"),
};

/**
 * Build the docker run arguments for the hardened container.
 * No credentials are passed — gateway handles authentication.
 */
function buildDockerArgs(config: ContainerConfig): string[] {
  const args: string[] = [
    "run",
    "--rm",
    "--name", `pipeline-run-${Date.now()}`,

    // User: nobody (uid=65534)
    "--user", "65534:65534",

    // Read-only root filesystem
    "--read-only",
    "--tmpfs", "/tmp:size=128m,uid=65534",

    // seccomp profile
    "--security-opt", `seccomp=${SECCOMP_PATH}`,
    "--security-opt", "no-new-privileges",

    // Drop ALL Linux capabilities
    "--cap-drop", "ALL",

    // Resource limits
    "--memory", `${config.maxMemoryMB}m`,
    "--cpus", String(config.maxCpuCores),

    // Environment — NO credentials
    "--env", `GATEWAY_URL=${config.gatewayUrl}`,
    "--env", "ANTHROPIC_API_KEY=",
    "--env", "TAVILY_API_KEY=",
    "--env", "PYTHONDONTWRITEBYTECODE=1",
    "--env", "PYTHONUNBUFFERED=1",
    "--env", "STRICT_NODE_GOVERNANCE=true",

    // Bind-mount logs directory (writable)
    "--volume", `${config.logsDir}:/app/logs`,

    // Network: internal only (requires gateway to be on same Docker network)
    "--network", "pipeline_internal",

    config.image,

    // Command arguments passed to main.py
    config.seedsPath,
  ];

  return args;
}

/**
 * Run the pipeline in an isolated container.
 * Returns stdout, stderr, exit code, and timing.
 */
export async function runInContainer(
  config: Partial<ContainerConfig> & { domain: string; seedsPath: string }
): Promise<ContainerResult> {
  const fullConfig: ContainerConfig = { ...DEFAULT_CONFIG, ...config };

  const startMs = Date.now();
  const dockerArgs = buildDockerArgs(fullConfig);

  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const proc: ChildProcess = spawn("docker", dockerArgs, {
      stdio: ["ignore", "pipe", "pipe"],
    });

    proc.stdout?.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr?.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });

    const timer = setTimeout(() => {
      timedOut = true;
      proc.kill("SIGKILL");
    }, fullConfig.timeoutSeconds * 1000);

    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve({
        exitCode: code ?? 1,
        stdout,
        stderr,
        durationMs: Date.now() - startMs,
        timedOut,
      });
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      resolve({
        exitCode: 1,
        stdout,
        stderr: `${stderr}\nProcess error: ${err.message}`,
        durationMs: Date.now() - startMs,
        timedOut: false,
      });
    });
  });
}

/**
 * Check that the Docker image exists and is up to date.
 * Throws if the image is not found.
 */
export function assertImageExists(image: string): void {
  try {
    execSync(`docker image inspect ${image}`, { stdio: "pipe" });
  } catch {
    throw new Error(
      `Docker image '${image}' not found. Build it first: docker build -f docker/Dockerfile -t ${image} .`
    );
  }
}

/**
 * Verify the seccomp profile exists before launching containers.
 */
export function assertSeccompProfile(): void {
  if (!fs.existsSync(SECCOMP_PATH)) {
    throw new Error(`seccomp profile not found at: ${SECCOMP_PATH}`);
  }
}
