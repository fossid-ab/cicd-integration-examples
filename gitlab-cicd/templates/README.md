# FossID GitLab CI templates

Four templates, each distributable on its own. Copy the one you want into a
repository, or `include:` it. None of them depends on another being present.

| Template | Answers | Needs |
| --- | --- | --- |
| [gitlab-diff-scan](gitlab-diff-scan/) | What open source did this merge request add? | `KB_URL`, `KB_TOKEN` |
| [gitlab-release-full-scan](gitlab-release-full-scan/) | What is in the release we are about to ship? | `WORKBENCH_URL`, `WORKBENCH_USER`, `WORKBENCH_TOKEN` |
| [code-quality-runner](code-quality-runner/) | Show a diff scan in the merge request widget | nothing |
| [notes-api-diff-runner](notes-api-diff-runner/) | Show it as merge request comments instead | `FOSSID_MR_TOKEN` |

## How they compose

The first two are independent scanners. The last two are renderers, and they
chain onto the diff scan through **files, not includes** — each reads an
artifact and writes one:

```
gitlab-diff-scan      →  fossid-diffscan.json
code-quality-runner   →  gl-code-quality-report.json    (MR widget + inline)
notes-api-diff-runner →  merge request threads

gitlab-release-full-scan  →  reports/*.xlsx, reports/*.spdx   (independent)
```

That is the whole contract. A renderer does not care what produced its input,
so either can be dropped into a pipeline that already has a scan step, or
replaced by something of your own that writes the same file. Both renderers
parse only the documented format — nothing FossID-shaped — so the decisions
about *what a finding says* stay in one place.

Running all three merge-request templates together is the full pipeline:

```yaml
stages: [scan, report]

include:
  - local: ci/fossid-diff-scan.gitlab-ci.yml
  - local: ci/fossid-code-quality.gitlab-ci.yml
  - local: ci/fossid-mr-notes.gitlab-ci.yml
```

then uncomment the `needs:` line in each renderer, so a job waits for its input
instead of racing it.

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
