#!/usr/bin/env node
// Informational report: do the components a PR introduces have known CVEs?
//
// This is deliberately NOT a gate. It answers a different question from the VSF
// check in vuln-severity-gate.mjs:
//
//   VSF        - "the code in this diff matches a known-vulnerable file"  (precise)
//   this report - "this diff pulls in a component that has known CVEs"    (broad)
//
// The second is broader and noisier, because a component-level CVE may affect a
// part of the component the diff never touches. It is also subject to diffscan
// reporting the *oldest* matching version of a component, which will not always be
// the version actually vendored. Useful as a signal, not as a pass/fail.
//
// Pipeline (see the workflow for how these are produced):
//   list-purls  diffscan report            -> unique purls of introduced components
//   list-cves   `component --bulk` output  -> unique CVE ids across those components
//   report      all three                  -> annotations + step summary, always exit 0

import { readFileSync, appendFileSync } from "node:fs";

const SEVERITY_RANK = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

function parseArgs(argv) {
  const mode = argv[0];
  if (!["list-purls", "list-cves", "report"].includes(mode)) {
    throw new Error(`expected 'list-purls', 'list-cves' or 'report', got ${mode ?? "nothing"}`);
  }
  const args = {
    mode,
    report: "license-report.json",
    components: "components.json",
    vulns: "component-vuln.json",
  };
  for (let i = 1; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--report") args.report = argv[++i];
    else if (arg === "--components") args.components = argv[++i];
    else if (arg === "--vulns") args.vulns = argv[++i];
    else throw new Error(`unknown argument: ${arg}`);
  }
  return args;
}

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

// `purl` is optional on a diffscan component and omitted when absent, so a diff can
// legitimately produce license issues that cannot be looked up at all.
function collectComponents(reportPath) {
  const issues = readJson(reportPath, {}).license_issues ?? [];
  const withPurl = new Map();
  const withoutPurl = [];

  for (const issue of issues) {
    const c = issue.component ?? {};
    const label = [c.author, c.artifact, c.version].filter(Boolean).join("/") || "(unknown)";
    if (c.purl) {
      if (!withPurl.has(c.purl)) withPurl.set(c.purl, { purl: c.purl, label, paths: new Set() });
      withPurl.get(c.purl).paths.add(issue.local_file?.path ?? "(unknown)");
    } else {
      withoutPurl.push(label);
    }
  }
  return { withPurl, withoutPurl: [...new Set(withoutPurl)] };
}

// The server ships component.cves as either ["CVE-..."] or [{id|cve_id: "CVE-..."}],
// and the bulk response may nest the component one level down. Handle both rather
// than guessing, and ignore anything that is not a CVE id.
function cvesForComponent(entry) {
  const raw = entry?.component?.cves ?? entry?.cves;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((v) => (typeof v === "string" ? v : (v?.id ?? v?.cve_id)))
    .filter((v) => typeof v === "string" && /^cve-/i.test(v));
}

// CVSS lives in different places depending on the age of the NVD record: prefer v3,
// fall back to v2, whose severity band sits one level up from its scores.
function extractSeverity(nvd) {
  const impact = nvd?.impact;
  const v3 = impact?.baseMetricV3?.cvssV3;
  if (v3) return { severity: v3.baseSeverity ?? null, score: v3.baseScore ?? null };
  const v2 = impact?.baseMetricV2;
  if (v2) return { severity: v2.severity ?? null, score: v2.cvssV2?.baseScore ?? null };
  return { severity: null, score: null };
}

function listPurls(args) {
  const { withPurl } = collectComponents(args.report);
  if (withPurl.size > 0) console.log([...withPurl.keys()].join("\n"));
  return 0;
}

function listCves(args) {
  const components = readJson(args.components, {});
  const cves = new Set();
  for (const entry of Object.values(components)) {
    for (const cve of cvesForComponent(entry)) cves.add(cve.toUpperCase());
  }
  if (cves.size > 0) console.log([...cves].join("\n"));
  return 0;
}

function report(args) {
  const { withPurl, withoutPurl } = collectComponents(args.report);

  if (withPurl.size === 0 && withoutPurl.length === 0) {
    console.log("No components introduced by this diff.");
    return 0;
  }

  const components = readJson(args.components, {});
  const vulns = readJson(args.vulns, {});

  const rows = [];
  for (const [purl, info] of withPurl) {
    const cves = cvesForComponent(components[purl])
      .map((id) => {
        const { severity, score } = extractSeverity(vulns[id.toUpperCase()]?.NVD);
        return { id, severity, score };
      })
      .sort((a, b) => SEVERITY_RANK.indexOf(b.severity) - SEVERITY_RANK.indexOf(a.severity));
    rows.push({ ...info, cves });
  }
  // Most-vulnerable components first.
  rows.sort((a, b) => b.cves.length - a.cves.length);

  const lines = [
    "## Components introduced by this PR",
    "",
    "_Informational only — this does not fail the build._",
    "",
    "Component-level CVEs may affect parts of a component this diff never touches,",
    "and the reported version is the **oldest** match, so treat these as leads to",
    "investigate rather than confirmed exposure.",
    "",
  ];

  let totalCves = 0;
  for (const row of rows) {
    if (row.cves.length === 0) {
      console.log(`::notice::${row.label} (${row.purl}) — no known CVEs`);
      continue;
    }
    totalCves += row.cves.length;
    const summary = row.cves
      .map((c) => `${c.id}${c.severity ? ` (${c.severity}${c.score ? ` ${c.score}` : ""})` : ""}`)
      .join(", ");
    for (const path of row.paths) {
      console.log(`::warning file=${path}::${row.label} has ${row.cves.length} known CVE(s): ${summary}`);
    }
  }

  lines.push("| Component | purl | Known CVEs |", "| --- | --- | --- |");
  for (const row of rows) {
    const cves = row.cves.length === 0
      ? "none"
      : row.cves
          .map((c) => `${c.id}${c.severity ? ` \`${c.severity}\`` : ""}`)
          .join("<br>");
    lines.push(`| ${row.label} | \`${row.purl}\` | ${cves} |`);
  }

  if (withoutPurl.length > 0) {
    lines.push(
      "",
      `${withoutPurl.length} component(s) had no purl and could not be looked up: ` +
        withoutPurl.map((c) => `\`${c}\``).join(", "),
    );
  }

  if (process.env.GITHUB_STEP_SUMMARY) {
    appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${lines.join("\n")}\n`);
  }

  console.log(
    `\n${rows.length} component(s) introduced, ${totalCves} known CVE(s) across them.` +
      (withoutPurl.length > 0 ? ` ${withoutPurl.length} component(s) had no purl to look up.` : ""),
  );
  return 0;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.mode === "list-purls") return listPurls(args);
  if (args.mode === "list-cves") return listCves(args);
  return report(args);
}

try {
  process.exit(main());
} catch (err) {
  console.error(`component-vuln-report: ${err.message}`);
  process.exit(2);
}
