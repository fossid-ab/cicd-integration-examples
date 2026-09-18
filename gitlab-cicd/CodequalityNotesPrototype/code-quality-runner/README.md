# Code Quality Creation Runner

Turns diffscan JSON into a GitLab Code Quality report.

A pure converter: reads a file, writes a file, makes no network calls. No
credentials, no scan server, any image with Python 3. That also makes it the
easy piece to embed in something larger — see
[Running it by hand](#running-it-by-hand).

```
fossid-diffscan.json  →  gl-code-quality-report.json  →  MR widget + inline in Changes
```

## Install

Copy `.gitlab-ci.yml` and `ci/fossid-codequality.py`, keeping the script at that
path or updating the path in the job.

Its input is whatever `fossid diffscan --format json` wrote — the
[gitlab-diff-scan](../gitlab-diff-scan/) template produces exactly that file, so
uncomment `needs: [toolbox-diffscan]` when using them together.

## Settings

No credentials. Everything is optional:

| Variable | Default | |
| --- | --- | --- |
| `FOSSID_RAW` | `fossid-diffscan.json` | Input |
| `FOSSID_REPORT` | `gl-code-quality-report.json` | Output |
| `FOSSID_COMMENT` | *(empty)* | Free-text note added to every finding |
| `FOSSID_FAIL_ON` | *(empty)* | `info`\|`minor`\|`major`\|`critical`\|`blocker`. Empty reports without gating |
| `FOSSID_CVE` | `off` | Note CVEs on findings. Only if the scan ran with `--vsf-mode new/all` |
| `WORKBENCH_SCAN_URL` | *(empty)* | Audit link added to every finding. Set by [workbench-mr-review](../workbench-mr-review/); empty omits the field |

`FOSSID_FAIL_ON` writes the report **before** deciding the exit code, so the
artifact survives a failing gate. This is the right place for a threshold — the
scan job deliberately does not gate, so that only real errors fail it.

## The action-needed link

Set `WORKBENCH_SCAN_URL` and every finding closes with a line naming where the
work gets done:

```
**Action needed**: Workbench Scan: https://workbench.example.com/nui/scans/1487/audit/pending
```

Nothing here produces that variable. [workbench-mr-review](../workbench-mr-review/)
does, as a dotenv artifact, and this template picks it up with no configuration.
Left empty the field is omitted entirely rather than rendered as a dead link, so
this stays correct on its own.

A dotenv variable reaches only the jobs that name its producer directly in
`needs:`, so wire this job to `wa-mr-review` — see that template's README.

## The default branch needs a pipeline, or the MR shows nothing

GitLab's Code Quality widget renders the **difference** between the MR's report
and the *target branch's* report. With no pipeline on the target branch there is
no base report, and the comparison returns nothing however many findings the MR
produced:

```
head_pipeline : 1 (success)   -> 12 degradations parsed
base_pipeline : nil           -> 0 pipelines on main
compare       : new=0  resolved=0  existing=0     -> widget empty
```

That is why the template includes a `toolbox-reference-report` job: it runs on
the default branch and publishes an empty report. Empty is correct rather than
lazy — with `--license-mode new` the scan already reports only what is absent
from the target branch, so the reference report is empty by construction and
costs no scan. After adding it:

```
base_pipeline : 3
summary       : {"total"=>12, "resolved"=>0, "errored"=>12}
new_errors    : 12            -> widget populated
```

If you switch the scan to `--license-mode all`, replace that job with a real
scan of the default branch, or the widget will report pre-existing debt as new.

**The MR's branch point matters too.** The base report is looked up at the
merge base SHA, so a branch created before the reference-report job existed
still has no base pipeline. Branch from a commit the default-branch pipeline
has run on.

**And so does the target branch.** The lookup is by merge-base SHA *and* ref,
matching the target branch — so an MR that targets anything other than the
default branch finds no reference report there and shows an empty widget,
however much the scan found:

```
MR !2  ProjectMix -> vendor-text-helpers        (42 findings in the head report)
diff_base_sha  : 17e27e64
pipelines at that sha:
  76  ref=refs/merge-requests/1/head  codequality=true   <- has a report, wrong ref
base_pipeline  : nil
compare        : {:status=>:parsing}      -> widget empty, no inline annotations
```

This is the confusing one, because the notes runner has no such dependency: its
threads appear on every finding as usual, so the scan visibly worked while the
widget looks like it missed everything.

If merge requests in your repository target long-lived branches, publish the
reference report on every branch instead of only the default one:

```yaml
toolbox-reference-report:
  rules:
    - if: $CI_COMMIT_BRANCH
```

It costs a 4-second job with `GIT_STRATEGY: none`, and under `--license-mode
new` the report is empty by construction either way. Existing MRs are not
retroactively fixed — their merge base still has no reference-report pipeline —
so an MR opened before the change needs a rebase onto a commit that has one, or
a retarget to a branch that does.

## Two places findings appear

| Where | Source |
| --- | --- |
| MR widget | A live comparison of the head report against the base report |
| Inline in **Changes** | A `code_quality_mr_diff` pipeline artifact, written after the pipeline finishes |

Neither needs enabling, and both work in CE. The inline artifact is produced by
`Ci::PipelineArtifacts::CreateQualityReportWorker`, enqueued automatically when
the pipeline completes. Its service applies three gates:

```ruby
return unless pipeline.can_generate_codequality_reports?   # a codequality report exists
return if pipeline.has_codequality_mr_diff_report?         # already built
return unless new_errors_introduced?                       # NEW vs the base report
```

That third gate is why the reference-report job matters twice over: without a
base pipeline there are no "new" errors, so **neither** the widget **nor** the
inline annotations appear.

Because the artifact is written after the pipeline completes, annotations show
up a few seconds after the widget. Querying too early returns
`status: :parsing` or zero files — the worker is still running, not failing.

## One finding per match, with the range in its name

```
major  src/mercury_core.c:1184   pkg:github/chromium/chromium@6.0.469.0 > BSD-3-Clause > lines 1184-1314 > partial
```

GitLab keeps `location.lines.begin` and **discards `end`** when building the
inline payload (`Gitlab::Ci::Reports::CodequalityMrDiff` keeps `line`,
`description` and `severity`), so the marker sits on one line however wide the
match is. The range therefore leads the description text, which is also the half
a truncating widget column keeps.

If you want the whole match highlighted, that is what the
[notes-api-diff-runner](../notes-api-diff-runner/) template is for.

`--annotate lines` instead emits one finding per line, marking every line of a
match at the cost of one widget row per line. Matches longer than
`--max-annotated-lines` (default 200) stay collapsed either way and say so in
the finding body, rather than being silently truncated.

Inline annotations only attach to files GitLab renders a diff for. A very large
file is collapsed and its annotations, though present in the artifact, are not
drawn until you expand it.

## Collapsing redundant matches

The same upstream code is routinely reported under several components. Findings
sharing a file and line range collapse into one; the survivor names a license
and lists the rest under **Also matched**.

## License policy is not evaluated here

The toolbox reads `.fossidpolicy` from the repository root and filters against
it *during the scan*, so everything reaching this converter has already passed
that gate. The converter only renders what it is given. Every finding gets the
same severity (`--severity`, default `major`) for the same reason: the policy
already decided what is worth reporting.

## Running it by hand

```bash
python3 ci/fossid-codequality.py diffscan.json -o report.json --pretty
python3 ci/fossid-codequality.py < diffscan.json > report.json
```

Exit codes: 0 success, 1 a `--fail-on` threshold was crossed, 2 the input was
not `diffscan --format json`. That last case explains what it got instead —
`--format human-readable` clips each finding to 20 source lines and
`--format github` carries anchor lines without ranges, so neither is accepted.

`--help` lists the rest.
