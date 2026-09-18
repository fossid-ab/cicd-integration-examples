# Workbench MR Review

Opens a merge request as a **Scan in Workbench**, so an auditor can work the
findings properly — while the developer keeps getting inline feedback in the
merge request.

Where [gitlab-diff-scan](../gitlab-diff-scan/) answers *what did this merge
request add?* and the two renderers show that answer to the developer, this
answers *where does someone actually resolve it?*

It also exports the link to that scan, so every finding the renderers produce
closes with a line naming where the work happens:

```
**Action needed**: Workbench Scan: https://workbench.example.com/nui/scans/1487/audit/pending
```

## Install

Copy `.gitlab-ci.yml` in as `ci/workbench-mr-review.gitlab-ci.yml` and
`include:` it.

Unlike the other four, this one is not useful alone: it reads
[gitlab-diff-scan](../gitlab-diff-scan/)'s report to decide the review scope, so
that template has to be in the pipeline too. Uncomment the `needs:` block on
`wa-mr-review` when you wire them together — see [Wiring](#wiring).

## CI/CD variables

Settings → CI/CD → Variables, all **Masked**.

| Variable | Value |
| --- | --- |
| `WORKBENCH_URL` | `https://workbench.example.com/api.php` — note the `/api.php` |
| `WORKBENCH_UI_URL` | Optional. Where a **human** opens Workbench, e.g. `https://workbench.example.com`. See [The audit link](#the-audit-link) |
| `WORKBENCH_USER` | Workbench username |
| `WORKBENCH_TOKEN` | Workbench API token |

The agent reads these from the environment, so they never appear in a command a
job log could echo. The job checks `WORKBENCH_URL` up front and fails with a
readable message rather than a stack trace.

## Settings

| Variable | Default | |
| --- | --- | --- |
| `WORKBENCH_MR_PROJECT` | `$CI_PROJECT_NAME-mr-review` | Workbench Project the review scans land in |
| `WORKBENCH_REUSE` | `--reuse-any-identification` | Reuse identifications from anywhere in Workbench |
| `WORKBENCH_UI_URL` | *(derived)* | Browser-facing base for the audit link |
| `FOSSID_RAW` | `fossid-diffscan.json` | The diff scan report to read the review scope from |

**Why a separate Workbench Project.** These are transient review scans, one per
merge request. Keeping them out of the Project that records releases leaves that
one a clean history of what actually shipped.

**Why reuse is on.** It is what makes a scan per merge request affordable:
anything already audited on the mainline comes back already identified, so what
stays pending is what this merge request genuinely introduces.

## What it exports

`WORKBENCH_SCAN_URL`, as a **dotenv** artifact.

[code-quality-runner](../code-quality-runner/) and
[notes-api-diff-runner](../notes-api-diff-runner/) both pick it up on their own —
neither needs configuring, and both omit the field entirely when the variable is
empty, so they stay correct without this template.

## Wiring

A dotenv variable reaches only the jobs that name the producing job **directly**
in `needs:`. It is not inherited down a chain, so `toolbox-mr-notes` does not get
it via `toolbox-codequality`. Both renderers have to name this job:

```yaml
toolbox-codequality:
  needs:
    - toolbox-diffscan
    - job: wa-mr-review
      optional: true

toolbox-mr-notes:
  needs:
    - toolbox-codequality
    - job: wa-mr-review
      optional: true
```

`optional: true` keeps the pipeline valid when this template is not included —
the variable is simply never set, and the findings carry no link.

`wa-mr-review` runs in the `scan` stage rather than `report`, because the
renderers consume what it exports. It only ever waited on `toolbox-diffscan`, so
running it earlier costs no wall-clock.

## The audit link

The scan id is read back out of the agent's **own output** rather than resolved
through the API: the agent already prints a `/nui/scans/<id>/` link, so a number
lifted from it needs no extra call and no second source of truth for which scan
this run touched.

Only the origin is swapped, via `WORKBENCH_UI_URL`. `WORKBENCH_URL` is the
address the *job* needs and is not necessarily one a browser can reach — on a
shared Docker network Workbench answers to its container name, which means
nothing on a reviewer's laptop. Left empty it is derived from `WORKBENCH_URL` by
dropping `/api.php`, which is right when both reach Workbench at the same
address.

If the agent prints no scan id, the job says so and carries on. A missing link
is not a broken review: the scan still exists and the findings still post.

## Review scope

Only the files the diff scan flagged are uploaded — not the whole repository.

They are taken from the scan report rather than from `git diff`, for two
reasons: it is the precise set the findings are about, and the agent image ships
no git. A file in the report that is not in the checkout is skipped with a note.

If nothing was flagged, no scan is opened and the job exits cleanly. An empty
merge request should not leave an empty scan behind for an auditor to wonder
about.

## Artifacts

```
workbench-scan.env   the dotenv carrying WORKBENCH_SCAN_URL
```

Written on every exit path, including the ones where no scan was opened, so the
variable is always defined and the renderers never see a half-configured
pipeline. It is written before the agent runs and overwritten after, rather than
only on success.
