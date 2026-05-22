/**
 * Audit log exporter for the Epistemic Sandbox Runtime.
 *
 * Validates pipeline run outputs against truthlens-audit-schema-v1.json
 * before writing to disk. Hard-fails on schema violations.
 *
 * Schema source: ../truthlens/truthlens-audit-schema-v1.json
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";
import addFormats from "ajv-formats";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_PATH = path.resolve(__dirname, "../../truthlens/truthlens-audit-schema-v1.json");
const AUDIT_DIR = path.resolve(__dirname, "../../logs/audit");

// ── Schema types ─────────────────────────────────────────────────────────────

export interface AuditProtocol {
  constitution_version: string;
  audit_schema_version: string;
  signals_registry_version: string;
}

export interface AuditArticle {
  url: string;
  title: string;
  timestamp: string;
}

export interface AuditSignal {
  id: string;
  score: number;
  label: string;
  [key: string]: unknown;
}

export interface AuditInterpretation {
  layer1: string;
}

export interface AuditRecord {
  protocol: AuditProtocol;
  article: AuditArticle;
  signals: AuditSignal[];
  interpretation: AuditInterpretation;
  known_limits: string[];
  exported_at: string;
}

// ── Validator ─────────────────────────────────────────────────────────────────

function buildValidator(): (data: unknown) => data is AuditRecord {
  const ajv = new Ajv({ strict: true, allErrors: true });
  addFormats(ajv);

  if (!fs.existsSync(SCHEMA_PATH)) {
    throw new Error(`Audit schema not found at: ${SCHEMA_PATH}`);
  }

  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8")) as object;
  const validate = ajv.compile<AuditRecord>(schema);

  return (data: unknown): data is AuditRecord => {
    const valid = validate(data);
    if (!valid && validate.errors) {
      const messages = validate.errors.map((e) => `  ${e.instancePath} ${e.message}`).join("\n");
      throw new Error(`Audit schema validation failed:\n${messages}`);
    }
    return valid;
  };
}

const validateAudit = buildValidator();

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Validate an audit record against the canonical schema.
 * Throws on any violation — callers must not write invalid records.
 */
export function validate(record: unknown): AuditRecord {
  if (!validateAudit(record)) {
    throw new Error("Audit record failed schema validation");
  }
  return record;
}

/**
 * Write a validated audit record to the audit log directory.
 * Filename: audit_<run_id>_<timestamp>.json
 */
export function writeAuditRecord(record: AuditRecord, runId: string): string {
  const validated = validate(record);

  fs.mkdirSync(AUDIT_DIR, { recursive: true });

  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `audit_${runId}_${ts}.json`;
  const outPath = path.join(AUDIT_DIR, filename);

  fs.writeFileSync(outPath, JSON.stringify(validated, null, 2), { encoding: "utf8", flag: "wx" });

  return outPath;
}

/**
 * Build an audit record from pipeline run output.
 * Maps pipeline state fields to the canonical schema.
 */
export function buildAuditRecord(params: {
  runId: string;
  domain: string;
  ritualCostScore: number;
  antiOptimizationScore: number;
  verdict: string;
  knownLimits: string[];
}): AuditRecord {
  const now = new Date().toISOString();

  return {
    protocol: {
      constitution_version: "1.0",
      audit_schema_version: "1",
      signals_registry_version: "1.0",
    },
    article: {
      url: `urn:pipeline:run:${params.runId}`,
      title: `Pipeline run — domain: ${params.domain}`,
      timestamp: now,
    },
    signals: [
      {
        id: "ritual_cost",
        score: params.ritualCostScore,
        label: "Ritual Cost Signal",
      },
      {
        id: "anti_optimization",
        score: params.antiOptimizationScore,
        label: "Anti-Optimization Signal",
      },
    ],
    interpretation: {
      layer1: params.verdict,
    },
    known_limits: params.knownLimits,
    exported_at: now,
  };
}

// ── CLI mode ──────────────────────────────────────────────────────────────────

if (process.argv[2] === "validate") {
  const inputPath = process.argv[3];
  if (!inputPath) {
    console.error("Usage: tsx src/audit.ts validate <path-to-audit.json>");
    process.exit(1);
  }
  try {
    const record = JSON.parse(fs.readFileSync(inputPath, "utf8")) as unknown;
    validate(record);
    console.log("PASS: Audit record conforms to truthlens-audit-schema-v1.json");
    process.exit(0);
  } catch (err) {
    console.error("FAIL:", err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}
