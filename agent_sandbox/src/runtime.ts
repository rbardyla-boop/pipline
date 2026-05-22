/**
 * Epistemic Sandbox Runtime — Node.js orchestrator.
 *
 * Execution flow:
 *   1. Pre-flight checks (image exists, seccomp profile, gateway reachable)
 *   2. Run pipeline in isolated container (docker + seccomp + read-only rootfs)
 *   3. Parse run output from logs/runs/
 *   4. Validate audit record against truthlens-audit-schema-v1.json (AJV)
 *   5. Write validated audit record to logs/audit/
 *   6. Exit with container exit code
 *
 * Usage:
 *   tsx src/runtime.ts <seeds-file> [--domain <domain>] [--image <image>]
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildAuditRecord, validate, writeAuditRecord } from "./audit.js";
import { runInContainer, assertImageExists, assertSeccompProfile } from "./container.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "../..");
const LOGS_DIR = path.join(PROJECT_ROOT, "logs");
const RUNS_DIR = path.join(LOGS_DIR, "runs");

const PIPELINE_KNOWN_LIMITS = [
  "Novelty scores are embedding-distance proxies, not ground-truth novelty measures",
  "Cultural simulation agents are stylised archetypes, not demographically validated populations",
  "Zeitgeist context is API-retrieved and may be stale, biased, or adversarially contaminated",
  "Phoenix rubric weights are heuristic — not derived from empirical outcome data",
  "Sandbox verdicts are simulations — real adoption patterns will differ",
];

// ── Argument parsing ──────────────────────────────────────────────────────────

interface RuntimeArgs {
  seedsFile: string;
  domain: string;
  image: string;
  gatewayUrl: string;
}

function parseArgs(): RuntimeArgs {
  const args = process.argv.slice(2);
  const seedsFile = args[0] ?? "seeds/gaming.yaml";

  const domainIdx = args.indexOf("--domain");
  const domain = domainIdx >= 0 ? (args[domainIdx + 1] ?? "gaming") : "gaming";

  const imageIdx = args.indexOf("--image");
  const image = imageIdx >= 0 ? (args[imageIdx + 1] ?? "pipline:latest") : "pipline:latest";

  const gatewayUrl = process.env["GATEWAY_URL"] ?? "http://localhost:8080";

  return { seedsFile, domain, image, gatewayUrl };
}

// ── Run output parser ─────────────────────────────────────────────────────────

interface RunOutput {
  run_id: string;
  domain: string;
  sandbox_verdict: string;
  best_concept_score: number;
  ritual_cost_score: number;
  anti_optimization_score: number;
}

function findLatestRunFile(): string | null {
  if (!fs.existsSync(RUNS_DIR)) return null;
  const files = fs.readdirSync(RUNS_DIR)
    .filter((f) => f.startsWith("full_run_") && f.endsWith(".json"))
    .map((f) => ({ name: f, mtime: fs.statSync(path.join(RUNS_DIR, f)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  return files[0] ? path.join(RUNS_DIR, files[0].name) : null;
}

function parseRunOutput(filePath: string): RunOutput {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8")) as unknown;
  if (!raw || typeof raw !== "object") throw new Error("Invalid run output");
  const r = raw as Record<string, unknown>;
  return {
    run_id: String(r["run_id"] ?? "unknown"),
    domain: String(r["domain"] ?? "unknown"),
    sandbox_verdict: String(r["sandbox_verdict"] ?? "SLOP"),
    best_concept_score: Number(r["best_concept_score"] ?? 0),
    ritual_cost_score: Number(r["ritual_cost_score"] ?? 0),
    anti_optimization_score: Number(r["anti_optimization_score"] ?? 0),
  };
}

// ── Gateway health check ──────────────────────────────────────────────────────

async function checkGateway(gatewayUrl: string): Promise<boolean> {
  try {
    const { default: http } = await import("node:http");
    const healthUrl = new URL("/health", gatewayUrl);
    return await new Promise((resolve) => {
      const req = http.get(healthUrl.toString(), (res) => {
        resolve((res.statusCode ?? 500) < 400);
      });
      req.on("error", () => resolve(false));
      req.setTimeout(3000, () => { req.destroy(); resolve(false); });
    });
  } catch {
    return false;
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = parseArgs();

  console.log("\n[SANDBOX RUNTIME] Epistemic Sandbox Runtime starting...");
  console.log(`  Image:     ${args.image}`);
  console.log(`  Seeds:     ${args.seedsFile}`);
  console.log(`  Domain:    ${args.domain}`);
  console.log(`  Gateway:   ${args.gatewayUrl}`);

  // Pre-flight checks
  assertSeccompProfile();
  console.log("[SANDBOX RUNTIME] seccomp profile: OK");

  assertImageExists(args.image);
  console.log("[SANDBOX RUNTIME] Docker image: OK");

  const gatewayOk = await checkGateway(args.gatewayUrl);
  if (!gatewayOk) {
    console.warn(`[SANDBOX RUNTIME] WARNING: Gateway not reachable at ${args.gatewayUrl}`);
    console.warn("[SANDBOX RUNTIME] Continuing — pipeline will use fallback signals");
  } else {
    console.log("[SANDBOX RUNTIME] Gateway health check: OK");
  }

  // Execute pipeline in isolated container
  console.log("\n[SANDBOX RUNTIME] Launching pipeline container...");
  const result = await runInContainer({
    domain: args.domain,
    seedsPath: args.seedsFile,
    image: args.image,
    gatewayUrl: args.gatewayUrl,
  });

  console.log(`\n[SANDBOX RUNTIME] Container exited: code=${result.exitCode} duration=${result.durationMs}ms`);

  if (result.timedOut) {
    console.error("[SANDBOX RUNTIME] FAIL: Container timed out");
    process.exit(1);
  }

  if (result.exitCode !== 0) {
    console.error("[SANDBOX RUNTIME] FAIL: Pipeline exited with non-zero code");
    console.error("STDERR:", result.stderr.slice(-2000));
    process.exit(result.exitCode);
  }

  // Parse run output and build audit record
  const runFile = findLatestRunFile();
  if (!runFile) {
    console.error("[SANDBOX RUNTIME] FAIL: No run output file found in logs/runs/");
    process.exit(1);
  }

  const runOutput = parseRunOutput(runFile);
  console.log(`[SANDBOX RUNTIME] Run output: ${runFile}`);

  const auditRecord = buildAuditRecord({
    runId: runOutput.run_id,
    domain: runOutput.domain,
    ritualCostScore: runOutput.ritual_cost_score,
    antiOptimizationScore: runOutput.anti_optimization_score,
    verdict: runOutput.sandbox_verdict,
    knownLimits: PIPELINE_KNOWN_LIMITS,
  });

  // Validate before writing (hard fail on schema violation)
  try {
    validate(auditRecord);
  } catch (err) {
    console.error("[SANDBOX RUNTIME] FAIL: Audit record schema violation:", err);
    process.exit(1);
  }

  const auditPath = writeAuditRecord(auditRecord, runOutput.run_id);
  console.log(`[SANDBOX RUNTIME] Audit record written: ${auditPath}`);
  console.log("[SANDBOX RUNTIME] All checks passed. Run complete.\n");

  process.exit(0);
}

main().catch((err) => {
  console.error("[SANDBOX RUNTIME] Unhandled error:", err);
  process.exit(1);
});
