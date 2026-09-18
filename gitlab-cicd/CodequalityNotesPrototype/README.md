# FossID GitLab CI templates

Five templates. Copy the one you want into a repository, or `include:` it.
The first four are distributable on their own and depend on nothing else being
present; the fifth reads the diff scan's report, so it wants that one alongside
it.

| Template | Answers | Needs |
| --- | --- | --- |
| [gitlab-diff-scan](gitlab-diff-scan/) | What open source did this merge request add? | `KB_URL`, `KB_TOKEN` |
| [gitlab-release-full-scan](gitlab-release-full-scan/) | What is in the release we are about to ship? | `WORKBENCH_URL`, `WORKBENCH_USER`, `WORKBENCH_TOKEN` |
| [code-quality-runner](code-quality-runner/) | Show a diff scan in the merge request widget | nothing |
| [notes-api-diff-runner](notes-api-diff-runner/) | Show it as merge request comments instead | `FOSSID_MR_TOKEN` |
| [workbench-mr-review](workbench-mr-review/) | Where does someone actually resolve it? | `WORKBENCH_URL`, `WORKBENCH_USER`, `WORKBENCH_TOKEN` |

Every folder has the same shape, so any one of them copies or zips on its own:

```
<template>/
  .gitlab-ci.yml    the jobs, with every setting commented at its default
  README.md         what it does, what it needs, and why it is built that way
  ci/*.py           only the two renderers have scripts; stdlib only
```

## How they compose

The first two are independent scanners. The last two are renderers, and they
chain onto the diff scan through **files, not includes** — each reads an
artifact and writes one:

```
gitlab-diff-scan      →  fossid-diffscan.json
code-quality-runner   →  gl-code-quality-report.json    (MR widget + inline)
notes-api-diff-runner →  merge request threads

workbench-mr-review   →  a Workbench Scan + WORKBENCH_SCAN_URL (dotenv)
                         which both renderers append to every finding

gitlab-release-full-scan  →  reports/  (xlsx, SPDX RDF, audit link)   (independent)
```

That is the whole contract. A renderer does not care what produced its input,
so either can be dropped into a pipeline that already has a scan step, or
replaced by something of your own that writes the same file. Both renderers
parse only the documented format — nothing FossID-shaped — so the decisions
about *what a finding says* stay in one place.

Running the merge-request templates together is the full pipeline:

```yaml
stages: [scan, report]

include:
  - local: ci/fossid-diff-scan.gitlab-ci.yml
  - local: ci/fossid-code-quality.gitlab-ci.yml
  - local: ci/fossid-mr-notes.gitlab-ci.yml
  - local: ci/workbench-mr-review.gitlab-ci.yml   # optional
```

then uncomment the `needs:` line in each renderer, so a job waits for its input
instead of racing it. With `workbench-mr-review` in the pipeline, both renderers
must name **that** job too — a dotenv variable reaches only the jobs that need
its producer directly, so `toolbox-mr-notes` does not inherit
`WORKBENCH_SCAN_URL` through `toolbox-codequality`. List it as
`optional: true` and the pipeline stays valid without it. Add the release template's `include:` alongside them and
nothing collides: it runs on tags, the renderers on merge requests, and the
Code Quality reference report on the default branch.

[`local-test/run-js-templates.sh`](../local-test/run-js-templates.sh) builds
exactly that — a project with the four core templates wired together — against a
local GitLab, if you want to watch it work before committing to it.
[`local-test/update-templates.sh`](../local-test/update-templates.sh) pushes a
later edit onto a branch of that project, adding `workbench-mr-review`, so a
change can be re-tested without rebuilding it.

## Picking a renderer

Both read the same report, so they never disagree. They are complementary
rather than alternatives — the widget is the at-a-glance count, the threads are
where a reviewer argues with a specific finding.

| | Code Quality | Diff threads |
| --- | --- | --- |
| Marks the whole match | No — GitLab keeps `begin` and discards `end` | Yes |
| Needs a pipeline on the default branch | Yes, or nothing renders at all | No |
| Resolvable | No | Yes |
| Survives after merge | No, the artifact expires | Yes |
| Extra credentials | None | A token with `api` scope |
| Noise | One widget list | One comment per finding, capped |

## The URL both renderers get wrong by default

Three templates build a URL for a human to click, and all default to an address
that a CI job can reach but a browser may not:

| Template | Variable | Defaults to | Symptom when wrong |
| --- | --- | --- | --- |
| notes-api-diff-runner | `FOSSID_API_URL` | `$CI_API_V4_URL` | `Connection refused` reading the MR |
| gitlab-release-full-scan | `WORKBENCH_UI_URL` | `WORKBENCH_URL` minus `/api.php` | A printed audit link nobody can open |
| workbench-mr-review | `WORKBENCH_UI_URL` | `WORKBENCH_URL` minus `/api.php` | Every finding points at a link nobody can open |

Both defaults are right when the runner and a browser reach the service at the
same address, and wrong the moment they do not — a Docker network, a reverse
proxy, split-horizon DNS, or an instance whose `external_url` says `localhost`.
Neither is a credential problem, so check them before regenerating tokens.

## Stages

Each template declares its own `stages:` so it runs standalone. When a template
is `include`d, the **including file's** `stages` wins and the ones declared in
the template are dropped — GitLab then rejects the pipeline with *chosen stage
does not exist* unless your pipeline has stages by those names. Either define
`scan` and `report`, or edit the `stage:` key in the jobs.

## Embedding in something larger

If you are wiring these into a bigger runner rather than using them as a
pipeline, the two Python scripts are the useful parts. Both are standard
library only, single file, no configuration file, and take everything by
argument or environment variable:

```bash
fossid diffscan ... --format json > raw.json
python3 fossid-codequality.py raw.json -o report.json
GITLAB_TOKEN=... python3 fossid-mr-notes.py report.json \
  --api "$CI_API_V4_URL" --project "$CI_PROJECT_ID" --mr "$CI_MERGE_REQUEST_IID"
```

Both exit 0 on success, 1 on a gate they were asked to enforce, and 2 on bad
input. `fossid-mr-notes.py --dry-run` writes nothing and reports what it would
post, which is the cheap way to check a wiring change.
