# GitLab Release Full Scan

Scans the **whole tree** with the Workbench agent when you cut a release, gates
on the result, and keeps the reports.

Where [gitlab-diff-scan](../gitlab-diff-scan/) answers *what did this merge
request add?*, this answers *what is in the thing we are about to ship?* — the
question an auditor, a customer questionnaire, or a court order asks.

Fully standalone: it shares no files with the other templates and talks to
Workbench rather than to the scan server the toolbox uses.

## Install

Copy `.gitlab-ci.yml` in as your pipeline, or as
`ci/fossid-release-full-scan.gitlab-ci.yml` and `include:` it.

## CI/CD variables

Settings → CI/CD → Variables, all **Masked**.

| Variable | Value |
| --- | --- |
| `WORKBENCH_URL` | `https://workbench.example.com/api.php` — note the `/api.php` |
| `WORKBENCH_UI_URL` | Optional. Where a **human** opens Workbench, e.g. `https://workbench.example.com`. See [the audit link](#the-audit-link) |
| `WORKBENCH_USER` | Workbench username |
| `WORKBENCH_TOKEN` | Workbench API token |

The agent reads all three from the environment, so they never appear in a
command a job log could echo. Each job checks them up front and fails with a
readable message rather than a stack trace.

## Settings

| Variable | Default | |
| --- | --- | --- |
| `WORKBENCH_PROJECT` | `$CI_PROJECT_NAME` | One Workbench Project per GitLab project |
| `WORKBENCH_SCAN` | *(derived)* | The tag on a release, `<branch>-<short sha>` on a merge to the mainline. Set it to pin one name |
| `WORKBENCH_REUSE` | `--reuse-any-identification` | Carry audit decisions forward |
| `WORKBENCH_GATE` | *(empty)* | What fails the pipeline. Empty only reports |
| `WORKBENCH_REPORT_TYPE` | `xlsx,spdx` | Blank downloads everything |
| `WORKBENCH_UI_URL` | *(derived)* | Browser-facing base for the audit link |

### The audit link

A release scan almost never comes back fully identified — the first one here
left 127 files pending. The pipeline therefore ends every job with a link
straight to the files still awaiting identification:

```
==============================================================
 Files awaiting identification:
   https://workbench.example.com/nui/scans/12/audit/pending
==============================================================
```

It is also written into the artifacts, next to the reports:

```
reports/workbench-pending.url   the bare URL
reports/workbench-pending.md    the same, as a markdown link
```

**Where the scan id comes from.** The agent already prints a
`/nui/scans/<id>/...` link of its own, so the id is lifted back out of its
output with `sed` rather than resolved through a second API call. One source of
truth for which scan this run touched, and no extra round trip.

**Why `WORKBENCH_UI_URL` exists.** Only the origin is replaced, because
`WORKBENCH_URL` is the address the *job* needs and not necessarily one a
reviewer's browser can resolve. Leave it empty and it is derived from
`WORKBENCH_URL` by dropping `/api.php`, which is right when both reach
Workbench at the same address. Set it when they differ — a Docker network, an
internal hostname, split-horizon DNS — or the pipeline will faithfully print a
link nobody can open. It is the same trap as `CI_API_V4_URL` in the
[notes-api-diff-runner](../notes-api-diff-runner/), from the same cause.

If the agent's output carries no scan id, the job says so and carries on:

```
workbench: no scan id in the agent output, so no audit link
```

A missing link is not a broken release, so it never fails the job.

### One Project, one Scan per tag or merge

Naming the Scan after the tag makes Workbench mirror your releases, so an
auditor can find the exact scan behind a shipped version. Keeping every release
in **one** Project is what makes `--reuse-any-identification` pay: an audit
decision made once for a component is not made again next release.

The name cannot simply be `$CI_COMMIT_TAG`, because that is empty on a branch
pipeline and the agent would be handed `--scan ""`. It is derived in the
`.workbench` `before_script` instead:

```sh
if [ -n "$CI_COMMIT_TAG" ]; then WB_SCAN="$CI_COMMIT_TAG"                    # a release
else WB_SCAN="${CI_COMMIT_REF_NAME}-${CI_COMMIT_SHORT_SHA}"; fi              # a merge
```

All three jobs recompute it rather than passing it along: they run in separate
containers, and every one of those variables is identical across a pipeline, so
the answer is the same without a hand-off that could go stale.

### Gating

`WORKBENCH_GATE` is empty by default, which reports without failing anything.
Start there — you cannot tell a useful threshold from a noisy one until you
have seen what a clean release looks like. Then tighten:

| Flag | Fails when |
| --- | --- |
| `--fail-on-pending` | Matches are still unreviewed |
| `--fail-on-policy` | A license policy rule is broken |
| `--fail-on-vuln-severity high` | A vulnerability at or above that severity exists |

Worth knowing what empty really means. A first scan of a real tree reports
something like:

```
Pending Files: 127 files  (warning)
Policy Warnings: 0
Vulnerabilities: 0
Overall Gate Status: PASSED
```

It passed **with 127 unreviewed files**, because nothing was asked to fail on
them. That is the correct default for a first run — but a release gate that
never sees `--fail-on-pending` is a gate that never blocks on unaudited code.
Add it once the pending count is down to something a human has actually looked
at — and note the gate job prints [the audit link](#the-audit-link) even when
it fails, which is the moment it is most useful.

## Job layout

```
scan    wa-release-scan      upload the tree, scan it
report  wa-release-gate      evaluate-gates
report  wa-release-reports   download xlsx/spdx   (runs even if the gate failed)
```

Three jobs rather than one script, for two reasons. A failed gate does not cost
you the scan, which is the expensive part. And the reports job runs `when:
always`, because a **blocked release is exactly when you want the spreadsheet
explaining what blocked it** — a gate failure with no evidence attached is a
dead end for whoever has to act on it.

## Artifacts

What `WORKBENCH_REPORT_TYPE: "xlsx,spdx"` actually produces, verified against
Workbench 2026.2.1:

```
reports/scan-v1_0_0-spdx.rdf    SPDX RDF/XML -- 298 files, 1 package
reports/scan-v1_0_0-xlsx.xlsx   a real workbook
reports/workbench-pending.url   link to the files awaiting identification
reports/workbench-pending.md    the same, as a markdown link
```

Note `spdx` means **RDF/XML**, not SPDX JSON. If a downstream consumer expects
`.spdx.json`, convert it or ask Workbench for a different type — do not assume
the extension from the type name.

`reports/` is kept with `expire_in: never`, unlike the week the merge-request
templates use. A release scan is the record of what you shipped and outlives
the merge request that led to it. If your instance has retention rules that
make `never` the wrong answer, set a long explicit period instead — but do not
leave it at the default.

## Runs on tags and on merges to the mainline

```yaml
rules:
  - if: $CI_COMMIT_TAG
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

Two things earn a full scan. A tag, because it is what you ship. And a merge to
the mainline, because that is the first moment the merged tree exists as a
whole — a diff scan only ever saw one side of it, and a clean merge of two
clean branches can still land a component neither of them introduced alone.

What makes the second affordable is `--reuse-any-identification`. Everything
audited on an earlier scan comes back already identified, so what stays pending
is what that merge actually introduced. Without reuse, a scan per merge would
re-ask the same questions every time and no one would keep it on.

`GIT_DEPTH: 0` because the agent uploads the working tree and needs a full
checkout — unlike a diff scan, which only needs the two refs.

Drop the second rule if a scan per merge is more than your Workbench wants; the
tag scan alone still records every release. Consider `--delta-scan` for the
mainline scans instead, which only sends files changed since the previous scan.
Leave it off for releases: a release scan should be complete, not incremental.

The jobs are named `wa-release-*` in both cases — `wa` for the Workbench agent
that runs them, as against the `toolbox-*` jobs driven by the Toolbox binary. A
mainline scan is the same operation with the same output as a release scan, a
record of one complete tree, so it earns no separate set of job names.

## Letting Workbench do the clone

For a large monorepo it is cheaper to have Workbench clone the repository
itself than to upload the tree from CI — `workbench-agent scan-git` instead of
`scan --path .`. It requires Workbench to be able to reach your GitLab, which
it cannot when GitLab is only on a laptop.
