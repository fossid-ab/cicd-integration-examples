---
name: fossid-workflow
description: >
    REQUIRED before calling scan_files, scan_signatures, or projectscan.
    Contains the workflow_ack token needed to authenticate scan calls
    and the mandatory pre-scan checklist (load policy, check graph state).
    Scan tools WILL REJECT calls without reading this skill first.
user-invokable: false
---

# fossid-workflow

Full FossID scan workflow: load the workspace policy, check graph state, run the appropriate scan tool, then highlight findings inline + in the Problems panel (via the in-process `fossid-editor` MCP server's `highlight_ranges` / `show_diagnostics` tools).

## Workflow — what to do when the user asks for a scan / audit

Read-only graph inspection (`graph_query`, `graph_export_raw`) is always
allowed. **Stateful operations** — `scan_files`, `scan_signatures`,
`projectscan`, `load_policy`, `generate_sbom`, etc. — are gated behind a
one-time session acknowledgement. Follow these steps in order:

1.  **Inspect the existing graph first** (no acknowledgement needed):

    ```cypher
    MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n
    ```

    The in-memory graph survives across requests within a session but dies
    on extension reload (see the host repo's `CLAUDE.md`). If `File`,
    `Component`, `Version` nodes already exist, the user's question may be
    answerable from the existing graph — try `graph_query` before
    triggering a fresh scan.

2.  **Acknowledge the workflow** before any stateful operation. Call
    `acknowledge_workflow` **once per session** with the token below:

    ```
    acknowledge_workflow(token: "fossid-workflow-v1")
    ```

    The acknowledgement persists for the session lifetime. Subsequent
    scan / load_policy / sbom calls don't need to repeat it. If you skip
    this step the server returns an error pointing back here.

    CI / SDK / Claude-Code-default hosts that don't ship this skill have
    the gate disabled server-side; the `acknowledge_workflow` call is
    harmless in those environments.

3.  **Load `.fossidpolicy` if the workspace has one.** Call `load_policy`
    with the policy file's absolute path so subsequent findings come back
    with the user's per-license / per-category actions (`allow` / `warn`
    / `error`) attached. The VS Code extension's Policies editor writes
    this file to the workspace root. Without it, findings have no policy
    verdict and the user can't act on them in the Problems panel.

    The file is the v0.6 schema (array of `{id, type, action, blocked, reason}` entries — see `docs/examples/fossidpolicy.example.json`). `load_policy` parses it server-side; the agent does not need to read the JSON itself.

4.  **Pick the right scan tool** based on the user's intent and inputs.
    **Prefer `projectscan` whenever the target is a directory** — it sees
    all files in one pass and can combine signal across them (cross-file
    component reconstruction, dependency resolution, license analysis),
    producing better matches than scanning files one-by-one:

    | Tool              | Use when                                                                                                                                                                                                 |
    | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `projectscan`     | **Default for any directory or repository scan.** Orchestrates content match + dependency resolution + license analysis with cross-file context. Strictly better than calling `scan_files` per-file.     |
    | `scan_files`      | A small, specific set of individual files — typically when the user names them explicitly ("scan src/foo.c"). For anything broader, switch to `projectscan` with the directory.                          |
    | `scan_signatures` | Pre-computed signatures already exist for the workspace files (faster than `scan_files`, but loses the cross-file benefit of `projectscan` — same trade-off applies: use `projectscan` for directories). |

5.  **Surface every finding to the user via diagnostics — not just chat.**
    After the scan completes, you MUST run the following mandatory queries
    and emit highlights + diagnostics for every result. A scan that returns
    findings but doesn't emit diagnostics is incomplete — the user can't
    navigate to or act on results that live only in your chat reply.

    **Mandatory query A — Policy-violated licenses (with byte ranges):**

    ```cypher
    MATCH (f:File)-[ll:LocalLicense]->(l:License)
    WHERE l.policy_status IN ['prohibited', 'conditional']
    RETURN f.path, l.spdx_id, l.policy_status, l.policy_action, ll.offset, ll.length
    ```

    For each row: `highlight_ranges` at `startByte = ll.offset`,
    `endByte = ll.offset + ll.length` with red (prohibited) or orange
    (conditional) color, plus `show_diagnostics` at the same range with
    severity `error` (prohibited) or `warning` (conditional). Message
    must include the SPDX ID and policy status.

    **Mandatory query B — Snippet matches (partial matches with byte ranges):**

    ```cypher
    MATCH (f:File)-[m:MatchedBy]->(v:Version)<-[:HasVersion]-(c:Component)
    OPTIONAL MATCH (v)-[:LicensedUnder]->(l:License)
    WHERE m.match_ranges IS NOT NULL
    RETURN f.path, c.name, v.version, v.id, l.spdx_id, v.cve_count,
           m.match_ranges, m.score, m.match_type
    ```

    For each row: parse `JSON.parse(m.match_ranges)` → emit one
    `highlight_ranges` entry per `{start_byte, end_byte}` pair. Color:
    red if `cve_count > 0`, otherwise license-family color. Also emit
    `show_diagnostics` at the same byte range. Message must name the
    component, version, and CVE count if nonzero.

    **Mandatory query C — Modified key license files:**

    ```cypher
    MATCH (f:File)-[ll:LocalLicense]->(l:License)
    WHERE ll.diff IS NOT NULL AND ll.modification > 0
    RETURN f.path, l.spdx_id, ll.offset, ll.length, ll.diff, ll.modification
    ```

    For each row with substantive diff entries (see "Classifying a
    LocalLicense diff" below): highlight + diagnose at the per-entry
    byte offsets from the parsed diff JSON.

    Run all three queries after every scan. Skip a query only if it
    returns zero rows. See "After scanning — highlighting findings"
    below for the full color / severity / message rules and templates.

### Workflow token

`fossid-workflow-v1` — the literal string to pass to `acknowledge_workflow`.
The token rotates on major workflow changes (suffix bumps: `v1` → `v2`
etc.). If the server rejects your acknowledgement with a "token mismatch"
error, re-read this section for the current value.

## After scanning — highlighting findings

Every fossid-mcp tool that produces license/component data populates the in-memory scan graph:

- `mcp_fossid-mcp_scan_files`, `mcp_fossid-mcp_scan_signatures`, `mcp_fossid-mcp_projectscan` — File / Component / Version / License nodes; `MatchedBy`, `LicensedUnder`, `LocalLicense`, `HeldBy` edges.
- `mcp_fossid-mcp_local_license_analysis` — File node + `LocalLicense` and `HeldBy` edges (license-text detections).
- `mcp_fossid-mcp_component_details` / `mcp_fossid-mcp_enrich_components` — enriches existing Version nodes (purl, cpes, homepage, author, release date).
- `mcp_fossid-mcp_resolve_dependencies` — `DependsOn` edges between Version nodes.

Drive every highlight from `mcp_fossid-mcp_graph_query` regardless of which tool ran.

## Two complementary tools — use BOTH

| Tool                                 | Purpose                            | User sees            |
| ------------------------------------ | ---------------------------------- | -------------------- |
| `mcp_fossid-editor_highlight_ranges` | Colored background + hover tooltip | Inline in editor     |
| `mcp_fossid-editor_show_diagnostics` | Warning/error entry                | Problems panel (⌘⇧M) |

Always create **both** a highlight and a diagnostic for each finding so the user gets visual context AND a navigable list.

## Color scheme by license family

Use these consistent colors so the user learns to recognize severity at a glance:

| Category                 | Color                           | When to use                                       |
| ------------------------ | ------------------------------- | ------------------------------------------------- |
| **Copyleft / strong**    | `rgba(255,0,0,0.3)` (red)       | GPL, AGPL, LGPL, EUPL, SSPL, OSL, CPAL, CC-BY-SA  |
| **Weak copyleft**        | `rgba(255,152,0,0.3)` (orange)  | MPL, EPL, CDDL, CPL, Artistic-2.0                 |
| **Permissive**           | `rgba(255,235,59,0.3)` (yellow) | BSD, MIT, Apache, ISC, Zlib, Unlicense, BSL, 0BSD |
| **Unknown / no license** | `rgba(156,39,176,0.3)` (purple) | No license detected, or license not in SPDX list  |
| **Clean / no issue**     | `rgba(76,175,80,0.3)` (green)   | Informational only, e.g. confirmed-OK components  |

When the license is ambiguous or dual-licensed, use the **most restrictive** category.

## Severity mapping for diagnostics

| Category             | Diagnostic severity |
| -------------------- | ------------------- |
| Copyleft / strong    | `error`             |
| Weak copyleft        | `warning`           |
| Permissive           | `warning`           |
| Unknown / no license | `warning`           |
| Clean / no issue     | `info`              |

## How to pick color and severity per finding type

The tables above describe the visual language. **Which rule applies depends on the finding type — a snippet match isn't itself a license, so picking its color requires more than a license lookup.** A snippet match is "this local code matches upstream code in component X v1.2"; the license belongs to the _component you matched_, not to the snippet.

### Snippet match (`scan_files` / `scan_signatures`, also `component_details` when it carries snippet data)

Two axes matter:

1. **Security risk first.** If `cve_count > 0` on the matched version → highlight is **red (`rgba(255,0,0,0.3)`)** and diagnostic severity is **`error`**, regardless of license family. A CVE-bearing BSD snippet is a worse problem than a CVE-free GPL snippet.
2. **Otherwise, license obligation.** Look up the **component's license** (`top_matches[].license`) in the color/severity tables. Frame the obligation as _"by including this code you've inherited license X's obligations"_ — there is no license inside the snippet itself.

Always name component + version in the hover/diagnostic. When CVEs are present, lead with the count (`⚠️ {cve_count} known vulnerabilities`).

### Modified or detected license (`local_license_analysis`)

The finding _is_ a license. Pick color and severity from the SPDX id against the tables — but **only after classifying the diff content** for license-text detections with `r.modification > 0`. Modification fraction alone is too coarse; small numeric differences often hide meaningful clause changes, and high numeric differences are sometimes pure noise (whitespace + year update across a long license).

#### Classifying a `LocalLicense` diff

Each entry in `JSON.parse(r.diff)` has:

- `change_type`: `"Added"` (in local but not canonical), `"Removed"` (in canonical but not local), `"Changed"` (semantic substitution).
- `reference`: canonical license text (`null` for Added).
- `actual`: text from the local file (`null` for Removed).
- `offset`, `length`: UTF-8 byte range of _this specific change_ in the local file (populated for Added / Changed; absent or zero for Removed since the text isn't in the local file). Use these as the highlight range when emitting the finding — one highlight + diagnostic per substantive entry, each pointing at its own bytes.

Walk the entries and decide per finding:

**Skip the diagnostic entirely** when every diff entry is one of:

- Copyright year update (`reference` and `actual` differ only by 4-digit year tokens).
- Copyright holder / project-name fill-in (placeholder like `<name of author>` or `[year]` replaced with a concrete value).
- Whitespace / line-break / trailing-punctuation differences only.
- Vendor reformatting that preserves all clause meanings (e.g. wrapping at a different column, changing `*` bullets to `-`).

**Emit at the SPDX-id severity** (license-family color, `error` for copyleft, `warning` for permissive) when any diff entry is:

- A removed clause that drops obligations — patent grants, attribution requirements, share-alike rules, anti-DRM language, defensive termination.
- An added restrictive clause (extra restrictions on use, distribution, modification, commercial use).
- A scope change ("this software" ↔ "this software and any derivative works").
- A license-family swap (e.g. GPL preamble replaced with MIT-like permissive boilerplate, or vice versa).

**Emit at `warning` (orange, weak-copyleft palette)** when:

- A `Changed` entry alters wording but you can't confidently classify the semantic effect — better surfaced for human review than silently dropped.
- Multiple small `Added`/`Removed` entries you can't categorise individually.

Lead the diagnostic message with what the diff actually changed, not the modification score. The score is a noisy summary; the diff is the evidence the user needs.

### Component-only finding (`component_details` without snippet data)

Same rules as snippet match (CVE override → red+error; otherwise component-license color), but you have no snippet location to highlight — emit a Problems-panel diagnostic only, no `highlight_ranges` call.

## Line/column vs byte offsets

The highlight and diagnostic tools accept **either** `startLine/endLine` or `startByte/endByte`. Prefer **byte offsets whenever the source tool reports them** — the extension converts to line/column internally using the file's current content (UTF-8 multi-byte and CRLF safe). **Never count lines yourself.**

> **Casing note**: fossid-mcp emits **snake_case** field names (`match_ranges`, `start_byte`, `end_byte`, `cve_count`). fossid-editor tool inputs are **camelCase** (`startByte`, `endByte`). Translate when calling the IDE tools — `start_byte` → `startByte`, `end_byte` → `endByte`.

**Rule of thumb**: every fossid-mcp tool that returns license/component data feeds the in-memory scan graph. **Use `graph_query` for everything** — snippet ranges, license-text ranges, CVE filters, dependency traversals. Inline tool responses (`top_matches`, `details_file`, `local_license_analysis` results, etc.) are transport conveniences, not the recommended source. One workflow, no exceptions.

Byte ranges live as edge properties on the graph:

- **`MatchedBy` edges (File → Version)** — `match_ranges` (JSON string). Snippet matches from `scan_files` / `scan_signatures` / `projectscan`. Parse with `JSON.parse(r.match_ranges)` to get `[{start_byte, end_byte}, ...]`. `null` = no ranges (whole-component or path-only match — skip highlight).
- **`LocalLicense` edges (File → License)** — edge-level `offset`, `length` (numeric) describe the _whole detected license region_; `diff` (JSON string) carries per-clause modifications when the local text differs from canonical. Each diff entry has its own `offset` and `length` for the specific change. **Prefer the per-entry ranges** for highlights when the diff has substantive entries — pointing at "added clause at byte 728, length 58" is the precise signal a user can act on; highlighting the whole 1500-byte license is noise. Fall back to the edge-level `r.offset` / `r.length` when `r.diff` is empty or absent (pristine match or no per-entry breakdown available).

### When to use which source

| Need                                                           | Use                                                         |
| -------------------------------------------------------------- | ----------------------------------------------------------- |
| Highlight snippet matches (any size, any filter)               | `graph_query` over `MatchedBy.match_ranges`                 |
| Highlight license-text detections                              | `graph_query` over `LocalLicense.{offset, length}`          |
| Component metadata not in the graph (purl, homepage, raw CVEs) | `component_details` (use the component `id` from the graph) |

## Hover message template (Markdown)

For highlights, use Markdown in the `message` field. When CVEs are present, lead with them so the user sees the security risk before the license framing.

**CVE-bearing snippet match (cve_count > 0):**

```markdown
⚠️ **{cve_count} known vulnerabilities** — {component} v{version}  
**License**: {license} (inherited from this component)  
**Score**: {score}
```

**Snippet match without CVEs:**

```markdown
**Snippet match**: {component} v{version}  
**License inherited**: {license}  
**Score**: {score}
```

Example (no CVEs):

```markdown
**Snippet match**: OpenFastPath/ofp v1.1  
**License inherited**: BSD-3-Clause  
**Score**: 1.0
```

Example (CVE-bearing):

```markdown
⚠️ **5 known vulnerabilities** — openssl/openssl v1.0.1a  
**License**: OpenSSL (inherited from this component)  
**Score**: 1.0
```

## Diagnostic message template

Keep it single-line for the Problems panel.

**CVE-bearing snippet match:**

```
⚠️ {cve_count} known vulnerabilities in {component} v{version} ({license}). Snippet match in this file at score {score}. {description_of_obligation}
```

**Snippet match without CVEs:**

```
{match_type} match: {component} v{version} ({license} — inherited), score {score}. {description_of_obligation}
```

Examples:

```
Snippet match: OpenFastPath/ofp v1.1 (BSD-3-Clause — inherited), score 1.0. By including this code you inherit BSD-3-Clause obligations: retain copyright notice and license text in distributions.
```

```
⚠️ 5 known vulnerabilities in openssl/openssl v1.0.1a (OpenSSL). Snippet match in this file at score 1.0. Review whether this version is still in use and consider upgrading.
```

## findingId convention

Use a stable, content-based ID so `sync` mode can track findings across re-scans. For snippet/component matches the ID is built from data on the **Version node**, not the edge — `MatchedBy` edges have no `id` property:

```
{r.match_type}#{c.name}#{v.id}
```

`v.id` is the 32-character hex on the Version node (e.g. `9ee28b6bd600a1696a9a88fb00000000`); `c.name` is the `author/artifact` string from the Component node; `r.match_type` is `partial` / `file` / `component` / `path_only`.

Example: `partial#OpenFastPath/ofp#9ee28b6bd600a1696a9a88fb00000000`

For `local_license_analysis` findings (LocalLicense edges): `license#{l.spdx_id}#{r.diff_fingerprint}`

## Source label

Always use `source: "FossID Scan"` for scan-based findings and `source: "FossID License"` for local license analysis findings. This groups them separately in the Problems panel.

## Step-by-step workflow

### After any FossID tool (unified workflow)

Every fossid-mcp tool that produces license/component data populates the graph: `scan_files`, `scan_signatures`, `projectscan`, `local_license_analysis`, `component_details`, `enrich_components`, `resolve_dependencies`. Drive every highlight from `graph_query` — the inline tool responses are transport conveniences, never the recommended source. Same workflow regardless of which tool ran.

**Schema reference** — the relationships you'll likely traverse:

| Relationship                                   | Direction           | Properties                                              |
| ---------------------------------------------- | ------------------- | ------------------------------------------------------- |
| `Component -[:HasVersion]-> Version`           | Component → Version | (none)                                                  |
| `Version -[:LicensedUnder]-> License`          | Version → License   | (none)                                                  |
| `File -[:MatchedBy]-> Version`                 | File → Version      | `match_ranges` (JSON string), `score`, `rank`, `source` |
| `Version -[:HasVulnerability]-> Vulnerability` | Version → CVE       | (none)                                                  |
| `File -[:LocalLicense]-> License`              | File → License      | `offset`, `length`, `modification`, `diff` (JSON), …    |

To get the component name for a Version, traverse `HasVersion` **backwards**: `(v:Version)<-[:HasVersion]-(c:Component)`.

The `graph_query` tool description in fossid-mcp lists the supported Cypher built-ins (`labels(n)`, `type(r)`, `keys(n)`, `id(n)`, etc.) and dialect notes — consult it for introspection helpers when you don't know the schema upfront.

1. **Query the graph** for everything you need to drive color/severity in one shot. Use `MatchedBy` for snippet matches, `LocalLicense` for license-text detections — pick whichever the highlight target is, or query both and union.

    Snippet matches (component-keyed). `MatchedBy.match_type` distinguishes `partial` (snippet), `file` (full-file), `component` (whole-component), `path_only`, and `noise` — filter on it; don't rely on `match_ranges IS NOT NULL` because non-noise file/component matches also have null ranges:

    ```cypher
    MATCH (f:File)-[r:MatchedBy]->(v:Version)<-[:HasVersion]-(c:Component)
    OPTIONAL MATCH (v)-[:LicensedUnder]->(l:License)
    WHERE r.match_type IN ['partial', 'file', 'component']
    RETURN f.path, c.name, v.version, v.id, l.spdx_id, v.cve_count, r.match_type, r.match_ranges, r.score
    ```

    License-text detections (file-keyed):

    ```cypher
    MATCH (f:File)-[r:LocalLicense]->(l:License)
    RETURN f.path, l.spdx_id, r.offset, r.length, r.modification, r.diff, r.diff_fingerprint
    ```

    Add `WHERE` clauses to filter (`WHERE v.cve_count > 0` for security-focused work, `WHERE r.modification > 0 AND r.diff IS NOT NULL` for tampered license texts — don't gate on a numeric threshold; small modification scores often hide meaningful diff content, let the diff itself drive the call, `WHERE c.name = 'openssl/openssl'` for a specific component, etc.).

2. **Convert each row to byte ranges**:
    - `MatchedBy.match_ranges`: `JSON.parse(r.match_ranges)` → `[{start_byte, end_byte}, ...]`. `null` for non-snippet matches (`r.match_type` is `file` / `component` / `path_only`) — these are file-level findings: call `show_diagnostics` with no position fields (omit `startLine`, `startByte`, etc.) and skip the `highlight_ranges` call. The IDE groups them under the file in the Problems panel.
    - `LocalLicense` with substantive entries in `r.diff` (after classification — see _"Classifying a LocalLicense diff"_): `JSON.parse(r.diff)` → walk the entries, drop benign ones, and emit **one highlight + one diagnostic per substantive entry** at `startByte = entry.offset`, `endByte = entry.offset + entry.length`. Each diagnostic message names what that specific entry changed (e.g. "Added clause restricting commercial use") so the Problems panel shows one navigable row per real issue.
    - `LocalLicense` with empty / absent `r.diff` (pristine match, or modification reported but no per-entry breakdown): single highlight + diagnostic at the whole region — `startByte = r.offset`, `endByte = r.offset + r.length`.

3. **Pick color and severity** per _"How to pick color and severity per finding type"_: for snippet matches, `cve_count > 0` → red + `error`, otherwise license-family color via `l.spdx_id`. For license-text detections with non-empty `r.diff`, **classify the diff first** (see _"Classifying a LocalLicense diff"_): skip benign updates, emit substantive changes at the SPDX-id severity, fall back to `warning` for ambiguous diffs.

4. **Call `highlight_ranges` once per file**, batching one entry per byte range. Group rows by `f.path`. Map `start_byte` → `startByte`, `end_byte` → `endByte`. Use the matching hover-message template (CVE-bearing variant if applicable).

5. **Call `show_diagnostics` once per file** with the same byte ranges, severity, message, and `findingId`.

### Multiple findings in one file

- Use `replace: true` (default) on the **first** call to clear stale highlights/diagnostics.
- Use `replace: false` on subsequent calls to **append** — OR batch all ranges into a single call (preferred).

Batching is preferred: pass all ranges in one `highlight_ranges` call and all diagnostics in one `show_diagnostics` call.

## Complete example — graph-driven highlighting

After `scan_files` (or any other scan) finishes, query the graph for highlight-worthy data. Note the snake_case field names from fossid-mcp; translate to camelCase when calling fossid-editor.

**Step 1 — `graph_query` call:**

```cypher
MATCH (f:File)-[r:MatchedBy]->(v:Version)<-[:HasVersion]-(c:Component)
OPTIONAL MATCH (v)-[:LicensedUnder]->(l:License)
RETURN f.path, c.name, v.version, l.spdx_id, v.cve_count, r.match_ranges, r.score
```

**Sample result rows** (illustrative — real output is JSON):

| f.path                  | c.name           | v.version | l.spdx_id    | v.cve_count | r.match_ranges                               | r.score |
| ----------------------- | ---------------- | --------- | ------------ | ----------- | -------------------------------------------- | ------- |
| /repo/src/example.c     | OpenFastPath/ofp | 1.1       | BSD-3-Clause | 0           | `"[{\"start_byte\":412,\"end_byte\":1730}]"` | 1.0     |
| /repo/src/sample_copy.c | torvalds/linux   | 3.9-rc5   | GPL-2.0-only | 4929        | `"[{\"start_byte\":0,\"end_byte\":4127}]"`   | 1.0     |

**Step 2 — parse `r.match_ranges`** for each row (`JSON.parse(...)`), drop rows where it's `null`.

**Step 3 — pick color/severity per row:**

- Row 1: `cve_count = 0`, license `BSD-3-Clause` → permissive yellow + `warning`.
- Row 2: `cve_count = 4929` → CVE override → red + `error` (regardless of GPL).

**Step 4 — `highlight_ranges` per file** (batched per `f.path`):

```json
{
    "uri": "/repo/src/example.c",
    "ranges": [
        {
            "startByte": 412,
            "endByte": 1730,
            "color": "rgba(255,235,59,0.3)",
            "message": "**Snippet match**: OpenFastPath/ofp v1.1\n**License inherited**: BSD-3-Clause\n**Score**: 1.0"
        }
    ]
}
```

```json
{
    "uri": "/repo/src/sample_copy.c",
    "ranges": [
        {
            "startByte": 0,
            "endByte": 4127,
            "color": "rgba(255,0,0,0.3)",
            "message": "⚠️ **4929 known vulnerabilities** — torvalds/linux v3.9-rc5\n**License**: GPL-2.0-only (inherited from this component)\n**Score**: 1.0"
        }
    ]
}
```

**Step 5 — `show_diagnostics` per file** with the same byte ranges, matching severity, and stable `findingId` (e.g. `snippet#torvalds/linux#<match_id>`).

If a row's `r.match_ranges` had multiple entries (discontinuous regions), batch them all into the same `highlight_ranges` call — one ranges array entry per byte range.

## License obligation descriptions

Append a brief obligation note to the diagnostic message:

| License family | Obligation note                                                                        |
| -------------- | -------------------------------------------------------------------------------------- |
| GPL/AGPL       | Copyleft: derivative works must be released under the same license.                    |
| LGPL           | Weak copyleft: linking is permitted but modifications to the library must be shared.   |
| MPL/EPL/CDDL   | File-level copyleft: modified files must be shared under the same license.             |
| BSD/MIT/ISC    | Permissive: retain copyright notice and license text in distributions.                 |
| Apache-2.0     | Permissive: retain notice, provide license text, state changes. Patent grant included. |
| Unknown        | License could not be determined — manual review required.                              |
