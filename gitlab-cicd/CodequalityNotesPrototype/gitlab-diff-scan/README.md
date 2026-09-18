# GitLab DiffScan

Scans what a merge request **changes** and writes the findings as JSON.

Nothing is rendered here. The whole output is one artifact,
`fossid-diffscan.json`, for a downstream job to turn into whatever your process
wants — the [code-quality-runner](../code-quality-runner/) and
[notes-api-diff-runner](../notes-api-diff-runner/) templates are two such jobs,
but so is anything of your own that reads the same file.

## Install

Copy `.gitlab-ci.yml` in as your pipeline, or as `ci/fossid-diff-scan.gitlab-ci.yml`
and `include:` it. Needs **fossid-toolbox 1.7+**, which is where `--format json`
arrives.

## CI/CD variables

Settings → CI/CD → Variables. Mark them **Masked**, and **Protected** if the
pipeline only runs on protected branches.

| Variable | Value |
| --- | --- |
| `KB_URL` | Scan server host, e.g. `eu1.foss.id` — host only, no `https://`, no trailing slash |
| `KB_TOKEN` | Scan server token |
| `QUAY_AUTH` | base64 of `username:password` for quay.io, to pull the image |

The job fails immediately with a readable message if `KB_URL` or `KB_TOKEN` is
missing, rather than letting the toolbox try to reach `https://scan/`.

GitLab has no inline `credentials:` key, so the image pull goes through
`DOCKER_AUTH_CONFIG`, which the template builds from `QUAY_AUTH`. If your runner
is already authenticated to quay.io, or you mirror the image internally, drop
that variable and point `FOSSID_IMAGE` wherever you keep it.

## Settings

| Variable | Default | |
| --- | --- | --- |
| `FOSSID_LICENSE_MODE` | `new` | `off` \| `new` \| `all`. `new` reports only what is absent from the target branch |
| `FOSSID_VSF_MODE` | `off` | Vulnerability scanning. Separately licensed, so opt in |
| `FOSSID_RAW` | `fossid-diffscan.json` | Output path |
| `FOSSID_IMAGE` | `quay.io/fossid/fossid-toolbox:latest` | Pin a tag for reproducibility |

### `FOSSID_VSF_MODE` and the empty-list trap

Left `off`, the output still carries `"vsf_issues": []` — byte-identical to a
scan that ran and found nothing. Downstream tooling must not read that as "no
CVEs", because nobody looked. Both renderer templates handle this by omitting
the CVE field entirely unless told the scan ran with it on.

## Why `--base-ref` takes a bare branch name

GitLab clones shallow and fetches only the MR source branch, so the target
branch is not in the runner's checkout. Given a bare name (`main`) the toolbox
fetches the missing ref itself — verified against a `--depth=1` clone. Given
`origin/main` it looks for a remote ref literally named `origin/main`, and
fails.

## Why no `--fail`

Findings should exit 0 so that only real errors — an unreachable server, a bad
token — fail this job. The threshold belongs downstream, on the rendered
report, where a human can see what tripped it:
`FOSSID_FAIL_ON` in the code-quality-runner does that.

## Output

One JSON document with `license_issues` and `vsf_issues`. Each issue carries a
`local_file.highlight.blocks[]` with a **0-based** `lines.offset` and a
`length`, so a block at offset 18 length 30 covers lines 19–48. Blocks are
discontinuous in practice — one match in testing covered lines 2–5850 and then
5884–5962 — so a consumer should treat each block as its own range rather than
flattening them into one span that swallows the gap.

`artifacts: when: always` so a failed scan still leaves behind whatever it
wrote, and so a downstream `needs:` does not fail for a missing file.
