#!/usr/bin/env python3
"""Post a GitLab Code Quality report as merge-request diff threads.

Reads a Code Quality report and posts one discussion thread per finding,
anchored to the lines that finding covers. Nothing FossID-shaped is parsed: the
input is a plain Code Quality array, so what a finding SAYS was decided
upstream and this tool only places it.

Deliberately minimal, to be dropped into a larger runner:

  * standard library only
  * one GET for the diff refs, one GET to deduplicate, one POST per finding
  * no diff parsing, no state kept anywhere but the merge request itself

Anchoring
---------
A diff note is accepted on an ADDED line -- a line in a new file, or a `+` line
-- when the position carries `new_line` and no `old_line`. That is what a
diffscan of a merge request mostly reports, because the licences it finds sit in
code the merge request adds.

An UNCHANGED line needs its old-side line number too, and the scan output does
not carry one; deriving it means fetching and parsing the MR diff. This tool
does not. It posts optimistically and lets GitLab reject what it cannot place.
The rejection is unambiguous (verified against GitLab 19.3.1 CE):

    400  Note {:line_code=>["can't be blank", "must be a valid line code"]}

Findings rejected that way -- on an unchanged line, in a file the MR does not
touch, or past the end of a file -- are collected into one summary comment
instead of being dropped.

Re-runs
-------
Every body ends with `<!-- fossid:<fingerprint> -->`, reusing the fingerprint
the report already carries. Existing threads are read once and matching
fingerprints skipped, so re-running on the same commit posts nothing.

Usage
-----
  fossid-mr-notes.py gl-code-quality-report.json           # CI_* env vars
  fossid-mr-notes.py report.json --project 21 --mr 1 --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MARKER = "<!-- fossid:{} -->"
MARKER_RE = re.compile(r"<!--\s*fossid:(\S+?)\s*-->")


def log(message):
    print(message, file=sys.stderr)


def call(args, method, path, data=None):
    """One GitLab API call. Returns (status, parsed body or error text)."""
    url = "{}/projects/{}/merge_requests/{}{}".format(
        args.api.rstrip("/"), urllib.parse.quote(str(args.project), safe=""),
        args.mr, path)
    body = urllib.parse.urlencode(data, doseq=True).encode() if data else None
    request = urllib.request.Request(
        url, data=body, method=method, headers={"PRIVATE-TOKEN": args.token})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
    except urllib.error.URLError as error:
        return 0, str(error.reason)


def position(refs, path, begin, end):
    """A text position on added lines, highlighting begin..end.

    The note anchors on the last line of the range; `line_range` is what makes
    GitLab draw the whole match rather than one line. `type: new` on both ends,
    and no `old_line` anywhere, is what marks these as added lines.
    """
    fields = {
        "position[base_sha]": refs["base_sha"],
        "position[start_sha]": refs["start_sha"],
        "position[head_sha]": refs["head_sha"],
        "position[position_type]": "text",
        "position[new_path]": path,
        "position[old_path]": path,
        "position[new_line]": end,
    }
    if end > begin:
        digest = hashlib.sha1(path.encode("utf-8")).hexdigest()
        fields.update({
            "position[line_range][start][line_code]":
                "{}_0_{}".format(digest, begin),
            "position[line_range][start][type]": "new",
            "position[line_range][start][new_line]": begin,
            "position[line_range][end][line_code]":
                "{}_0_{}".format(digest, end),
            "position[line_range][end][type]": "new",
            "position[line_range][end][new_line]": end,
        })
    return fields


def where(issue):
    """(path, begin, end) for a finding, or None if it carries no location."""
    location = issue.get("location") or {}
    lines = location.get("lines") or {}
    path, begin = location.get("path"), lines.get("begin")
    if not path or not begin:
        return None
    end = lines.get("end") or begin
    return path, begin, max(end, begin)


def body(issue):
    """The thread text: the finding's own words, then its fingerprint marker."""
    heading = issue.get("description") or issue.get("check_name") or "finding"
    parts = ["**{}**".format(heading)]
    detail = (issue.get("content") or {}).get("body")
    if detail:
        parts.append(detail)
    parts.append(MARKER.format(issue.get("fingerprint") or "-"))
    return "\n\n".join(parts)


def summary(unplaced, workbench_url=""):
    """One merge-request comment for the findings no position could hold."""
    rows = ["**FossID findings not anchored inline**", "",
            "| Severity | File | Lines | Finding |", "| --- | --- | --- | --- |"]
    for issue, span, reason in unplaced:
        if span:
            path, begin, end = span
            lines = "{}-{}".format(begin, end) if end > begin else str(begin)
        else:
            path, lines = "-", "-"
        rows.append("| {} | `{}` | {} | {} |".format(
            issue.get("severity", "-"), path, lines,
            (issue.get("description") or "").replace("|", "\\|")))
    # Inline threads carry this inside each finding's own body; the summary
    # has no finding body to inherit it from, so it is added once here.
    if workbench_url:
        rows += ["", "**Action needed**: Workbench Scan: {}".format(workbench_url)]
    rows += ["", "These sit on unchanged lines, in files this merge request "
                 "does not touch, or past a limit. " + MARKER.format("summary")]
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Post a GitLab Code Quality report as merge-request diff "
                    "threads. Anchors on added lines; anything else is listed "
                    "in one summary comment.")
    parser.add_argument("report", nargs="?",
                        help="Code Quality report (default: stdin)")
    parser.add_argument("--api", default=os.environ.get("CI_API_V4_URL"),
                        help="API root (default: $CI_API_V4_URL)")
    parser.add_argument("--project", default=os.environ.get("CI_PROJECT_ID"),
                        help="project id or path (default: $CI_PROJECT_ID)")
    parser.add_argument("--mr", default=os.environ.get("CI_MERGE_REQUEST_IID"),
                        help="merge request iid (default: $CI_MERGE_REQUEST_IID)")
    parser.add_argument("--token", default=os.environ.get("GITLAB_TOKEN"),
                        help="token with api scope (default: $GITLAB_TOKEN). "
                             "CI_JOB_TOKEN cannot write notes.")
    parser.add_argument("--max-threads", type=int, default=25, metavar="N",
                        help="stop after N threads (default: 25, 0 for no "
                             "limit). The rest go to the summary comment.")
    parser.add_argument("--no-summary", dest="summary", action="store_false",
                        help="drop unplaceable findings instead of listing them")
    parser.add_argument("--workbench-url", default="", metavar="URL",
                        help="browser-facing Workbench Scan URL, added to the "
                             "summary comment as the action needed. Inline "
                             "threads already carry it when the report was "
                             "built with fossid-codequality.py --workbench-url, "
                             "since a thread renders the finding body verbatim.")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any finding could not be anchored")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be posted; writes nothing")
    args = parser.parse_args()

    missing = [name for name, value in (("--api", args.api),
                                        ("--project", args.project),
                                        ("--mr", args.mr)) if not value]
    if not args.token:
        missing.append("--token/GITLAB_TOKEN")
    if missing:
        parser.error("missing: " + ", ".join(missing))

    text = open(args.report, encoding="utf-8").read() if args.report \
        else sys.stdin.read()
    issues = json.loads(text) if text.strip() else []
    if not isinstance(issues, list):
        log("toolbox-mr-notes: ERROR - expected a Code Quality array")
        return 2
    if not issues:
        log("toolbox-mr-notes: no findings, nothing to post")
        return 0

    status, mr = call(args, "GET", "")
    if status != 200 or not isinstance(mr, dict) or not mr.get("diff_refs"):
        log("toolbox-mr-notes: ERROR - cannot read MR !{}: {} {}".format(
            args.mr, status, str(mr)[:200]))
        return 2
    refs = mr["diff_refs"]

    # Fingerprints already on the merge request, so a re-run is a no-op. One
    # page: past 100 threads the duplicate risk matters less than the calls.
    seen = set()
    status, threads = call(args, "GET", "/discussions?per_page=100")
    if status == 200 and isinstance(threads, list):
        for thread in threads:
            for note in thread.get("notes") or []:
                seen.update(MARKER_RE.findall(note.get("body") or ""))
    if seen:
        log("toolbox-mr-notes: {} finding(s) already on this MR".format(
            len(seen - {"summary"})))

    posted = skipped = 0
    unplaced = []
    for issue in issues:
        if issue.get("fingerprint") in seen:
            skipped += 1
            continue
        span = where(issue)
        if not span:
            unplaced.append((issue, None, "no location"))
            continue
        if args.max_threads and posted >= args.max_threads:
            unplaced.append((issue, span, "over the thread limit"))
            continue
        path, begin, end = span
        if args.dry_run:
            log("  would post {}:{}-{}".format(path, begin, end))
            posted += 1
            continue
        payload = position(refs, path, begin, end)
        payload["body"] = body(issue)
        status, response = call(args, "POST", "/discussions", payload)
        if status == 201:
            posted += 1
        elif status == 400 and "line_code" in str(response):
            # Not an added line, or not in this diff at all. Expected.
            unplaced.append((issue, span, "not an added line in this diff"))
        else:
            unplaced.append((issue, span, "rejected ({})".format(status)))
            log("  {} {}:{} {}".format(status, path, end, str(response)[:160]))

    if unplaced and args.summary:
        if args.dry_run:
            log("  would post a summary for {} finding(s)".format(len(unplaced)))
        elif "summary" in seen:
            log("toolbox-mr-notes: summary comment already present, not reposting")
        else:
            status, response = call(args, "POST", "/notes",
                                    {"body": summary(unplaced, args.workbench_url)})
            if status != 201:
                log("toolbox-mr-notes: summary failed: {} {}".format(
                    status, str(response)[:160]))

    log("toolbox-mr-notes: {}{} thread(s), {} already present, {} in the "
        "summary".format("would post " if args.dry_run else "posted ",
                         posted, skipped, len(unplaced)))
    return 1 if unplaced and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
