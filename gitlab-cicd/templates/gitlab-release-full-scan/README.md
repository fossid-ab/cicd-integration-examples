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
| `WORKBENCH_USER` | Workbench username |
| `WORKBENCH_TOKEN` | Workbench API token |

The agent reads all three from the environment, so they never appear in a
command a job log could echo. Each job checks them up front and fails with a
readable message rather than a stack trace.

## Settings

| Variable | Default | |
| --- | --- | --- |
| `WORKBENCH_PROJECT` | `$CI_PROJECT_NAME` | One Workbench Project per GitLab project |
| `WORKBENCH_SCAN` | `$CI_COMMIT_TAG` | One Scan per release |
| `WORKBENCH_REUSE` | `--reuse-any-identification` | Carry audit decisions forward |
| `WORKBENCH_GATE` | *(empty)* | What fails the pipeline. Empty only reports |
| `WORKBENCH_REPORT_TYPE` | `xlsx,spdx` | Blank downloads everything |

### One Project, one Scan per tag

Naming the Scan after the tag makes Workbench mirror your releases, so an
auditor can find the exact scan behind a shipped version. Keeping every release
in **one** Project is what makes `--reuse-any-identification` pay: an audit
decision made once for a component is not made again next release.

### Gating

`WORKBENCH_GATE` is empty by default, which reports without failing anything.
Start there — you cannot tell a useful threshold from a noisy one until you have
seen what a clean release looks like. Then tighten:

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
at.

## Job layout

```
scan    workbench-release-scan      upload the tree, scan it
report  workbench-release-gate      evaluate-gates
report  workbench-release-reports   download xlsx/spdx        (runs even if the gate failed)
```

Three jobs rather than one script, for two reasons. A failed gate does not cost
you the scan, which is the expensive part. And the reports job runs
`when: always`, because a **blocked release is exactly when you want the
spreadsheet explaining what blocked it** — a gate failure with no evidence
attached is a dead end for whoever has to act on it.

## Artifacts

What `WORKBENCH_REPORT_TYPE: "xlsx,spdx"` actually produces, verified against
Workbench 2026.2.1:

```
reports/scan-v1_0_0-spdx.rdf    SPDX RDF/XML -- 298 files, 1 package
reports/scan-v1_0_0-xlsx.xlsx   a real workbook
```

Note `spdx` means **RDF/XML**, not SPDX JSON. If a downstream consumer expects
`.spdx.json`, convert it or ask Workbench for a different type — do not assume
the extension from the type name.

`reports/` is kept with `expire_in: never`, unlike the week the merge-request
templates use. A release scan is the record of what you shipped and outlives the
merge request that led to it. If your instance has retention rules that make
`never` the wrong answer, set a long explicit period instead — but do not leave
it at the default.

## Runs on tags

`rules: - if: $CI_COMMIT_TAG`. `GIT_DEPTH: 0` because the agent uploads the
working tree and needs a full checkout — unlike a diff scan, which only needs
the two refs.

To also scan every merge to the mainline, add:

```yaml
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

to the `.workbench` rules. Consider `--delta-scan` for those, which only sends
files changed since the previous scan and keeps per-commit scans cheap. Leave it
off for releases: a release scan should be complete, not incremental.

## Letting Workbench do the clone

For a large monorepo it is cheaper to have Workbench clone the repository itself
than to upload the tree from CI — `workbench-agent scan-git` instead of `scan
--path .`. It requires Workbench to be able to reach your GitLab, which it
cannot when GitLab is only on a laptop.
