# Notes API Diff Runner

Posts a GitLab Code Quality report to a merge request as **diff threads**, one
per finding, anchored to the lines it covers.

```
gl-code-quality-report.json  →  POST /merge_requests/:iid/discussions
```

Its input is a plain Code Quality report — the
[code-quality-runner](../code-quality-runner/) template writes exactly that
file. The script parses nothing FossID-specific, so any Code Quality report
works whatever produced it, and every decision about *what a finding says*
stays upstream in one place.

## Deliberately minimal

This is the piece most likely to end up inside a larger runner, so it is kept
as small as the job allows:

- Standards library only. One file, 264 lines, over a third of which is documentation.
- **No diff parsing.** It posts optimistically and lets GitLab reject what it
  cannot place (see below).
- No state anywhere but the merge request itself.
- Three kinds of API call: one `GET` for the diff refs, one `GET` to
  deduplicate, one `POST` per finding.

Everything comes from arguments or environment variables, there is no config
file, and `--dry-run` reports what it would post without writing anything.

## Install

Copy `.gitlab-ci.yml` and `ci/fossid-mr-notes.py`. Set `FOSSID_MR_TOKEN`.

| Variable | Default | |
| --- | --- | --- |
| `FOSSID_MR_TOKEN` | — | **Required.** Token with `api` scope |
| `FOSSID_REPORT` | `gl-code-quality-report.json` | Input |
| `FOSSID_NOTES_MAX` | `25` | Findings past this go to one summary comment |
| `FOSSID_API_URL` | `$CI_API_V4_URL` | Override when the runner cannot reach that address |
| `WORKBENCH_SCAN_URL` | *(empty)* | Audit link added to the summary comment. Set by [workbench-mr-review](../workbench-mr-review/); empty omits it |

In CI the target is taken from `CI_API_V4_URL`, `CI_PROJECT_ID` and
`CI_MERGE_REQUEST_IID`, so there is usually nothing else to configure.

### When `CI_API_V4_URL` is not reachable from the job

`CI_API_V4_URL` is built from the instance's `external_url` — the address a
**browser** uses. A job container does not necessarily resolve it. The symptom
is unmistakable:

```
toolbox-mr-notes: ERROR - cannot read MR !1: 0 [Errno 111] Connection refused
```

Set `FOSSID_API_URL` to an address the runner can reach. This bites whenever
the runner talks to GitLab by another name — split-horizon DNS, a reverse
proxy, or a Docker network where `external_url` says `localhost`. It is not a
credential problem, so check it before regenerating tokens.

## The action-needed link

Set `WORKBENCH_SCAN_URL` and the summary comment closes with a line naming where the
work gets done:

```
**Action needed**: Workbench Scan: https://workbench.example.com/nui/scans/1487/audit/pending
```

Nothing here produces that variable. [workbench-mr-review](../workbench-mr-review/)
does, as a dotenv artifact, and this template picks it up with no configuration.
Inline threads already carry it, since a thread renders the finding's own body
verbatim and the report was built with it. The summary comment has no finding
body to inherit from, which is why it is passed here too. Left empty the line is
omitted entirely.

A dotenv variable reaches only the jobs that name its producer directly in
`needs:`, so wire this job to `wa-mr-review` — see that template's README.

## The token

`CI_JOB_TOKEN` has no write access to notes, so the job needs a real one:

- **Project access token** — Settings → Access tokens, role Reporter or above,
  scope `api`. Comments appear as `@project_NN_bot`. This is the right choice.
- A **group access token**, if several projects share the pipeline.
- A personal access token works but attributes every comment to a human, which
  makes the audit trail worse.

The job fails readably if the variable is unset, and is `allow_failure: true`:
an expired token should cost you comments, not a merge request.

## Which lines a thread can anchor to

A diff note is rejected unless the position matches how that line appears in the
diff. Verified against GitLab 19.3.1 CE:

| Line | Position must carry | |
| --- | --- | --- |
| **Added** — in a new file, or a `+` line | `new_line` only | sending `old_line` too → 400 |
| **Unchanged** | `new_line` **and** the correct `old_line` | `new_line` alone → 400 |
| Unchanged, outside every diff hunk | same | accepted; GitLab unfolds the diff |
| Past end of file | — | 400 |

**This template only anchors added lines**, which is what a diff scan of a
merge request mostly reports — the licenses it finds sit in code the MR adds,
and a vendored file is added whole.

An unchanged line needs its old-side number, which the scan output does not
carry; deriving it means fetching and parsing the MR diff to map every new-side
line back to its old-side counterpart. That is real complexity for a case this
input rarely produces, so instead the tool posts and lets GitLab refuse:

```
400  Note {:line_code=>["can't be blank", "must be a valid line code"]}
```

The refusal is unambiguous, costs one call, and is caught by status and message
rather than guessed at.

### The whole match is highlighted

`position[line_range]` carries the start and end, so a 131-line match
highlights 131 lines. This is the main thing diff threads do that the Code
Quality report cannot — GitLab keeps `begin` and discards `end` there, so the
same finding marks a single line.

The note anchors on the **last** line of the range, with `line_range` spanning
back to the first. `line_code` is `sha1(new_path)_0_<new_line>`; the `0` is the
old-side number, which added lines do not have.

## Findings it cannot place

Collected into **one** merge-request comment with a table of severity, file,
lines and finding — never dropped silently. That covers unchanged lines, files
the MR does not touch, lines past end of file, and anything over
`FOSSID_NOTES_MAX`.

`--no-summary` drops them instead. `--strict` exits 1 if there were any, for a
pipeline that would rather know.

## Re-runs

Every thread body ends with `<!-- fossid:<fingerprint> -->`, reusing the
fingerprint the Code Quality report already carries. Existing threads are read
once and matching fingerprints skipped, so re-running on the same commit posts
nothing:

```
toolbox-mr-notes: 1 finding(s) already on this MR
toolbox-mr-notes: posted 0 thread(s), 1 already present, 0 in the summary
```

One page of discussions is read, not all of them — past 100 threads on a single
merge request, the duplicate risk matters less than the API calls.

Note that threads are **not** resolved when a finding goes away: a fixed finding
leaves its thread behind, marked outdated by GitLab once the line moves. If you
want stale threads resolved automatically, that needs a `PUT` per thread and a
full listing to be sure — deliberately out of scope here.

## Volume

One thread per finding, capped at 25. Run the converter with `--annotate match`
(its default) if you enable this: `--annotate lines` explodes each match into
one finding per line, which here would mean one comment per line.

## Running it by hand

```bash
export GITLAB_TOKEN=glpat-...
python3 ci/fossid-mr-notes.py gl-code-quality-report.json \
  --api https://gitlab.example.com/api/v4 --project 21 --mr 1 --dry-run
```

`--dry-run` writes nothing and reports what it would post. It still needs a
token, because it reads the merge request to get its diff refs.

Exit codes: 0 success, 1 `--strict` and something went to the summary, 2 bad
input or an unreadable merge request.
