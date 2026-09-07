#!/usr/bin/env python3
"""Convert `fossid-toolbox diffscan --format json` licence findings into a
GitLab Code Quality report.

License compliance only. `vsf_issues` (CVEs) are ignored if present; run the
scan with `--vsf-mode off` so they are not produced in the first place.

Requires toolbox 1.7 or newer, which is where `--format` arrives. Earlier builds
can only emit a human-readable report (clipped to the first 20 source lines of
each finding) or GitHub-style `::error` annotations (one anchor line per finding,
no ranges); neither is accepted here.

The JSON is one document holding `license_issues`. Each issue carries `local_file.highlight.blocks[]` with a 0-based `lines.offset` and a
`length`, so findings get exact line ranges -- and multiple blocks per issue,
which is how a discontinuous match is expressed. Nothing is read from disk.

License policy is NOT evaluated here. The toolbox reads .fossidpolicy from the
repository root and filters against it during the scan, so everything reaching
this converter has already passed that gate. This tool only renders what it is
given, and every license finding carries the same severity -- DEFAULT_SEVERITY
below, or whatever --severity says. Vulnerability findings are the one exception;
see severity_for.

Usage:  fossid-codequality.py diffscan.json -o gl-code-quality-report.json
        fossid-codequality.py < diffscan.json > gl-code-quality-report.json
"""

import argparse
import hashlib
import json
import sys

SEVERITY_ORDER = ["info", "minor", "major", "critical", "blocker"]

# The one severity every license finding gets, unless --severity says otherwise.
DEFAULT_SEVERITY = "major"

# What a finding is escalated to when VSF data is consulted and the match
# carries a known CVE. Only reachable via --cve-severity; see severity_for.
DEFAULT_CVE_SEVERITY = "critical"


def log(message):
    print(message, file=sys.stderr)


def fingerprint(*parts):
    return hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def location(path, begin, end):
    lines = {"begin": begin}
    if end and end > begin:
        lines["end"] = end
    return {"path": path, "lines": lines}


def span_label(begin, end, whole_file=False):
    """"whole file" / "lines N-M" / "line N", to lead the description with.

    GitLab shows only `description`, and draws its marker on the begin line, so
    the range has to be in the text or the reader cannot see how far the match
    extends. Leading with it keeps it readable when the widget truncates.

    A whole-file match says so. It arrives with no highlight blocks at all --
    there is no range to report because the range is the file -- and the
    location falls back to line 1 so GitLab has something to anchor. Calling
    that "line 1" would understate an entirely third-party file as a one-line
    finding, which is the opposite of what it is.
    """
    if whole_file:
        return "whole file"
    if end and end > begin:
        return "lines {}-{}".format(begin, end)
    return "line {}".format(begin)


def emit(issues, template, path, begin, end, expand, cap):
    """Append one finding per range, or one per line when expanding.

    GitLab draws inline annotations from `location.lines.begin` only --
    `Gitlab::Ci::Reports::CodequalityMrDiff` keeps `line`, `description` and
    `severity` and discards `end`. So a range emitted as a single finding marks
    exactly one line in the Changes view, however wide the range is. Marking a
    whole match therefore means emitting a finding per line.

    Ranges longer than `cap` stay collapsed to a single finding: expanding a
    5,000-line match would bury both the diff and the MR widget. The finding
    says so rather than silently truncating.
    """
    span = (end or begin) - begin + 1
    if not expand or span <= 1:
        issues.append(dict(template, location=location(path, begin, end)))
        return

    if span > cap:
        note = ("Spans {} lines ({}-{}); above the {}-line annotation limit, so "
                "only the first line is marked.".format(span, begin, end, cap))
        body = template["content"]["body"]
        issues.append(dict(
            template,
            content={"body": body + "\n\n" + note if body else note},
            location=location(path, begin, end)))
        return

    for line in range(begin, (end or begin) + 1):
        issues.append(dict(
            template,
            location=location(path, line, None),
            fingerprint=fingerprint(template["fingerprint"], line)))


def component_name(component):
    if not component:
        return None
    if component.get("purl"):
        return component["purl"]
    author, artifact = component.get("author"), component.get("artifact")
    if author and artifact:
        return "{}/{}@{}".format(author, artifact, component.get("version", "?"))
    return artifact or author


def license_ids(container):
    """SPDX ids from a {"licenses": [{"id": ...}]} block."""
    return [l["id"] for l in (container or {}).get("licenses") or [] if l.get("id")]


def component_license_ids(component):
    ids = []
    for entry in (component or {}).get("license_files") or []:
        ids.extend(license_ids(entry))
    return ids


def line_ranges(node):
    """(begin, end) 1-based inclusive line ranges from a highlight block.

    `lines.offset` is 0-based, so a block at offset 18 length 30 covers lines
    19..48. Blocks are discontinuous in practice -- one match in testing covered
    lines 2-5850 and then 5884-5962 -- so each block becomes its own finding
    rather than being flattened into one span that swallows the gap.
    """
    ranges = []
    for block in ((node or {}).get("highlight") or {}).get("blocks") or []:
        lines = block.get("lines") or {}
        offset, length = lines.get("offset"), lines.get("length")
        if offset is None:
            continue
        begin = offset + 1
        ranges.append((begin, begin + max(length or 1, 1) - 1))
    return ranges


def cve_index(document):
    """path -> [(begin, end, cve_id)] from vsf_issues.

    These are never findings of their own. They answer one question per license
    match: does the matched code carry a known CVE?

    Only consulted when the caller opts in with --cve, because `--vsf-mode off`
    still emits `"vsf_issues": []` -- byte-identical to a scan that ran and found
    nothing. Reading that as "no CVEs" would state a result nobody checked, and
    vulnerability scanning is separately licensed, so it may not be available at
    all. Without the opt-in the field is omitted rather than guessed.
    """
    index = {}
    for issue in document.get("vsf_issues") or []:
        local = issue.get("local_file") or {}
        path, cve = local.get("path"), issue.get("cve_id")
        if not path or not cve:
            continue
        for begin, end in line_ranges(local) or [(1, None)]:
            index.setdefault(path, []).append((begin, end or begin, cve))
    return index


def cves_for(index, path, begin, end):
    """CVE ids whose range overlaps this match."""
    last = end or begin
    return sorted({cve for (cb, ce, cve) in index.get(path, [])
                   if cb <= last and ce >= begin})


def severity_for(severity, cves, cve_severity):
    """The single place a finding's severity is decided.

    License findings are all the same severity. Ranking them here would mean
    re-deciding what .fossidpolicy already decided during the scan, and a
    second opinion could only disagree with it -- so there is no
    copyleft-vs-permissive table, just `severity`.

    VSF findings are the exception the flat rule has to leave room for: a CVE
    is a graded fact about the matched code, not a policy judgement, so a match
    overlapping one can legitimately outrank a clean match. That only applies
    when vulnerability data was actually consulted (--cve) and the caller asked
    for the escalation (--cve-severity); otherwise the flat severity stands.

    `cves` is [] both when nothing overlapped and when nothing was scanned, so
    it is never read without cve_severity having been set deliberately.
    """
    if cve_severity and cves:
        return cve_severity
    return severity


def blank_group():
    return {"file_licenses": set(), "component_licenses": set(),
            "components": set(), "types": set(), "urls": set()}


def convert(document, expand=False, cap=200, severity=DEFAULT_SEVERITY,
            comment="", cve=False, cve_severity=None):
    """Build Code Quality issues from the `license_issues` of a scan.

    Findings sharing a file and line range collapse into one, because the same
    upstream code is routinely reported under several components; the survivor
    names the most restrictive license and lists the rest.
    """
    grouped = {}

    for issue in document.get("license_issues") or []:
        local = issue.get("local_file") or {}
        path = local.get("path")
        if not path:
            continue
        component = issue.get("component") or {}
        remote = issue.get("remote_file") or {}
        file_licenses = license_ids(remote)
        comp_licenses = component_license_ids(component)
        for span in line_ranges(local) or [None]:  # None = whole-file match
            found = grouped.setdefault((path, span), blank_group())
            found["file_licenses"].update(file_licenses)
            found["component_licenses"].update(comp_licenses)
            name = component_name(component)
            if name:
                found["components"].add(name)
            if issue.get("match_type"):
                found["types"].add(issue["match_type"])
            if remote.get("url"):
                found["urls"].add(remote["url"])

    index = cve_index(document) if cve else None
    issues = []
    for (path, span), found in sorted(grouped.items(),
                                      key=lambda kv: (kv[0][0], kv[0][1] or (0, 0))):
        # A whole-file match has no blocks, so it groups under span None and
        # anchors at line 1 -- but it is not a line-1 finding. See span_label.
        whole_file = span is None
        begin, end = span if span else (1, None)
        components = sorted(found["components"])
        primary = components[0] if components else "unknown component"
        licenses = sorted(found["file_licenses"] | found["component_licenses"])
        license_text = ", ".join(licenses) if licenses else "unknown license"
        match_type = "/".join(sorted(found["types"])) or "match"
        upstream = sorted(found["urls"])

        # component > license > lines > match type > [CVE] > comment
        label = span_label(begin, end, whole_file)
        fields = [primary, license_text, label, match_type]
        body = ["**Component**: `{}`".format(primary),
                "**License**: {}".format(license_text),
                "**Lines matched**: {}".format(label),
                "**Match type**: `{}`".format(match_type)]
        cves = cves_for(index, path, begin, end) if index is not None else []
        if index is not None:
            cve_text = ", ".join(cves) if cves else "none"
            fields.append("CVE: " + cve_text)
            body.append("**CVE**: {}".format(cve_text))
        if comment:
            fields.append(comment)
        if len(components) > 1:
            body.append("**Also matched**: {}".format(", ".join(components[1:6])))
        if upstream:
            body.append("**Upstream**: {}".format(upstream[0]))
        # Always present, so downstream tooling can rely on the field existing.
        body.append("**Comment**: {}".format(comment or "-"))

        emit(issues, {
            "type": "issue",
            "check_name": "fossid-license",
            "description": " > ".join(fields),
            "content": {"body": "\n\n".join(body)},
            "categories": ["Compatibility"],
            "severity": severity_for(severity, cves, cve_severity),
            "fingerprint": fingerprint("license", path, license_text, primary, begin),
        }, path, begin, end, expand, cap)
    return issues


WRONG_FORMAT = (
    "fossid-codequality: ERROR - input is not `diffscan --format json` output.\n"
    "  Re-run the scan with --format json (requires toolbox 1.7+).\n"
    "  --format human-readable clips each finding to 20 source lines, and\n"
    "  --format github carries anchor lines without ranges; neither is accepted."
)


def load_document(text):
    """Parse the scan output, or exit 2 explaining what was expected instead."""
    try:
        document = json.loads(text)
    except ValueError:
        log(WRONG_FORMAT)
        if "License issue found" in text or "VSF issue found" in text:
            log("  (this looks like the human-readable report)")
        elif "::error file=" in text:
            log("  (this looks like --format github annotations)")
        return None
    if not isinstance(document, dict) or not (
            "license_issues" in document or "vsf_issues" in document):
        log(WRONG_FORMAT)
        log("  (parsed as JSON, but has no license_issues / vsf_issues key)")
        return None
    return document


def main():
    parser = argparse.ArgumentParser(
        description="Convert the license findings of `fossid-toolbox diffscan "
                    "--format json` (toolbox 1.7+) into a GitLab Code Quality "
                    "report. License compliance only; CVEs are ignored. "
                    "License policy is applied by the toolbox during the scan, "
                    "not here."
    )
    parser.add_argument("input", nargs="?",
                        help="diffscan --format json output (default: stdin)")
    parser.add_argument("-o", "--output", help="report path (default: stdout)")
    parser.add_argument("--fail-on", choices=SEVERITY_ORDER,
                        help="exit 1 if any issue is at least this severe. The "
                             "report is written first, so the artifact survives.")
    parser.add_argument("--cve", action="store_true",
                        help="add a CVE field to each finding, from the scan's "
                             "vsf_issues. Off by default: vulnerability scanning "
                             "is separately licensed, and `--vsf-mode off` "
                             "produces the same empty vsf_issues as a scan that "
                             "found none, so the field is omitted rather than "
                             "asserting 'none' without having looked.")
    parser.add_argument("--severity", choices=SEVERITY_ORDER,
                        default=DEFAULT_SEVERITY,
                        help="severity for every finding (default: {}). "
                             "Findings are not ranked by license: the policy "
                             "already decided what gets "
                             "reported.".format(DEFAULT_SEVERITY))
    parser.add_argument("--cve-severity", choices=SEVERITY_ORDER,
                        nargs="?", const=DEFAULT_CVE_SEVERITY,
                        help="report findings that overlap a known CVE at this "
                             "severity instead of --severity ({} if the flag is "
                             "given no value). Needs --cve, since that is what "
                             "reads vsf_issues; without it every finding keeps "
                             "the one flat severity.".format(
                                 DEFAULT_CVE_SEVERITY))
    parser.add_argument("--comment", default="",
                        help="free-text note appended to every finding, for "
                             "whatever your process needs to say.")
    parser.add_argument("--annotate", choices=["match", "lines"], default="match",
                        help="'match' (default) emits one finding per match, "
                             "carrying its full line range. GitLab draws the "
                             "inline marker from the begin line only, so the "
                             "range shows in the finding text rather than as a "
                             "highlight. 'lines' instead emits one finding per "
                             "line, which marks every line but turns one match "
                             "into many rows in the MR widget.")
    parser.add_argument("--max-annotated-lines", type=int, default=200,
                        metavar="N",
                        help="matches longer than N lines stay collapsed to a "
                             "single finding (default: 200).")
    parser.add_argument("--pretty", action="store_true",
                        help="indent the report. Default is compact, which is "
                             "smaller to upload and parse.")
    args = parser.parse_args()

    # Escalation reads vsf_issues, which only --cve does. Say so rather than
    # letting a set flag quietly do nothing.
    if args.cve_severity and not args.cve:
        log("fossid-codequality: --cve-severity ignored without --cve; every "
            "finding keeps '{}'".format(args.severity))
        args.cve_severity = None

    if args.input:
        with open(args.input, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()

    # An empty scan is a success with nothing to say, not a format error.
    if not text.strip():
        issues = []
        log("fossid-codequality: empty input, no issues")
    else:
        document = load_document(text)
        if document is None:
            return 2
        issues = convert(document, expand=args.annotate == "lines",
                         cap=args.max_annotated_lines, severity=args.severity,
                         comment=args.comment, cve=args.cve,
                         cve_severity=args.cve_severity)
        log("fossid-codequality: read {} license issue(s)".format(
            len(document.get("license_issues") or [])))
        # Only a hint for a mismatched setup: the scan paid for vulnerability
        # data that the report was not told to use. Silent in the normal case,
        # where --vsf-mode is off and there is nothing to ignore.
        ignored = len(document.get("vsf_issues") or [])
        if ignored and not args.cve:
            log("fossid-codequality: scan produced {} vsf issue(s); pass --cve "
                "to note them on findings, or set --vsf-mode off".format(ignored))

    issues.sort(key=lambda i: (i["location"]["path"],
                               i["location"]["lines"]["begin"]))
    payload = json.dumps(issues, indent=2) if args.pretty \
        else json.dumps(issues, separators=(",", ":"))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)

    counts = {}
    for item in issues:
        counts[item["severity"]] = counts.get(item["severity"], 0) + 1
    summary = ", ".join("{} {}".format(counts[s], s)
                        for s in SEVERITY_ORDER if s in counts)
    log("fossid-codequality: {} finding(s){} - {:,} bytes".format(
        len(issues), " ({})".format(summary) if summary else "", len(payload)))

    if args.fail_on:
        threshold = SEVERITY_ORDER.index(args.fail_on)
        failing = [i for i in issues
                   if SEVERITY_ORDER.index(i["severity"]) >= threshold]
        if failing:
            log("fossid-codequality: failing, {} finding(s) at or above "
                "'{}'".format(len(failing), args.fail_on))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
