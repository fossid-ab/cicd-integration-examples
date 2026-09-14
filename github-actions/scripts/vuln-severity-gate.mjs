#!/usr/bin/env node
// Gate a pull request on vulnerabilities introduced by its diff.
//
// `fossid diffscan` reports *which* CVEs a diff introduces, but its JSON carries only
// cve_id/cve_url per finding — no severity. `fossid vuln` resolves ids to full NVD
// records. This script is the join between the two, and does no network I/O itself.
//
//   list-cves  read a diffscan report, print unique CVE ids (one per line)
//   gate       join report + vuln output, annotate, and decide pass/fail
//
// See .github/workflows/pr-vsf-severity-gate.yml for how the pieces fit together.

import { readFileSync, appendFileSync } from "node:fs";

// Ranked low to high, so comparing against a threshold is an index compare.
const SEVERITY_RANK = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

function parseArgs(argv) {
  const mode = argv[0];
  if (!["list-cves", "gate"].includes(mode)) {
    throw new Error(`expected 'list-cves' or 'gate' as first argument, got ${mode ?? "nothing"}`);
  }
  const args = {
    mode,
    report: "vsf-report.json",
    vulns: "vuln.json",
    minSeverity: "HIGH",
    failOnUnknown: false,
  };
  for (let i = 1; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--report") args.report = argv[++i];
    else if (arg === "--vulns") args.vulns = argv[++i];
    else if (arg === "--min-severity") args.minSeverity = String(argv[++i]).toUpperCase();
    else if (arg === "--fail-on-unknown") args.failOnUnknown = true;
    else throw new Error(`unknown argument: ${arg}`);
  }
  if (!SEVERITY_RANK.includes(args.minSeverity)) {
    throw new Error(
      `--min-severity must be one of ${SEVERITY_RANK.join(", ")}, got ${args.minSeverity}`,
    );
  }
  return args;
}

function readVsfIssues(path) {
  return JSON.parse(readFileSync(path, "utf8")).vsf_issues ?? [];
}

// CVSS sits in different places depending on the age of the NVD record. Prefer v3 and
// fall back to v2, where the severity band lives one level up from the scores.
function extractSeverity(nvd) {
  const impact = nvd?.impact;
  const v3 = impact?.baseMetricV3?.cvssV3;
  if (v3) return { severity: v3.baseSeverity ?? null, score: v3.baseScore ?? null };

  const v2Block = impact?.baseMetricV2;
  if (v2Block) return { severity: v2Block.severity ?? null, score: v2Block.cvssV2?.baseScore ?? null };

  return { severity: null, score: null };
}

function renderSummary(findings, args, blocking) {
  const lines = [
    "## FossID VSF gate",
    "",
    `Threshold: fail on **${args.minSeverity}** or higher` +
      `${args.failOnUnknown ? ", and on unresolved severity" : ""}.`,
    "",
    `${findings.length} vulnerable file match(es), ${blocking.size} blocking.`,
    "",
    "| | CVE | Severity | CVSS | File |",
    "| --- | --- | --- | --- | --- |",
  ];
  for (const f of findings) {
    const mark = blocking.has(f) ? "❌" : "⚠️";
    lines.push(
      `| ${mark} | [${f.cveId}](${f.cveUrl}) | ${f.severity ?? "unknown"} | ${f.score ?? "-"} | \`${f.path}\` |`,
    );
  }
  return lines.join("\n");
}

function listCves(args) {
  const cves = [...new Set(readVsfIssues(args.report).map((i) => i.cve_id).filter(Boolean))];
  if (cves.length > 0) console.log(cves.join("\n"));
  return 0;
}

function gate(args) {
  const issues = readVsfIssues(args.report);
  if (issues.length === 0) {
    console.log("No vulnerable files introduced by this diff. Gate passed.");
    return 0;
  }

  // Absent when there were no CVEs to resolve, so treat a missing file as "no data"
  // rather than an error — every finding then falls through to the unknown path.
  let vulnData = {};
  try {
    vulnData = JSON.parse(readFileSync(args.vulns, "utf8"));
  } catch {
    console.log(`No vulnerability data at ${args.vulns}; severities will be unresolved.`);
  }

  const findings = issues.map((issue) => {
    const { severity, score } = extractSeverity(vulnData?.[issue.cve_id]?.NVD);
    return {
      cveId: issue.cve_id,
      cveUrl: issue.cve_url,
      path: issue.local_file?.path ?? "(unknown)",
      severity,
      score,
    };
  });
  // Worst first, so the most serious finding is the first thing read in the log.
  findings.sort((a, b) => SEVERITY_RANK.indexOf(b.severity) - SEVERITY_RANK.indexOf(a.severity));

  const threshold = SEVERITY_RANK.indexOf(args.minSeverity);
  const blocking = new Set(
    findings.filter((f) =>
      f.severity === null ? args.failOnUnknown : SEVERITY_RANK.indexOf(f.severity) >= threshold,
    ),
  );

  for (const f of findings) {
    // ::error / ::warning annotate the file inline in the PR's Files tab.
    const level = blocking.has(f) ? "error" : "warning";
    const sev = f.severity ?? "unknown severity";
    const score = f.score === null ? "" : `, CVSS ${f.score}`;
    console.log(`::${level} file=${f.path}::${f.cveId} (${sev}${score}) - ${f.cveUrl}`);
  }

  if (process.env.GITHUB_STEP_SUMMARY) {
    appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${renderSummary(findings, args, blocking)}\n`);
  }

  if (blocking.size > 0) {
    console.error(`\nGate failed: ${blocking.size} of ${findings.length} finding(s) at or above ${args.minSeverity}.`);
    return 1;
  }
  console.log(`\nGate passed: ${findings.length} finding(s) recorded, none at or above ${args.minSeverity}.`);
  return 0;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  return args.mode === "list-cves" ? listCves(args) : gate(args);
}

try {
  process.exit(main());
} catch (err) {
  console.error(`vuln-severity-gate: ${err.message}`);
  process.exit(2);
}
