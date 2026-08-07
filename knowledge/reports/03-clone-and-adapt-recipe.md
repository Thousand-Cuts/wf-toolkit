# 03 — Clone and Adapt (Cross-Environment Recipe)

Cross-environment report lifecycle: pull a known-good report from a source environment, sanitise environment-specific values out of the JSON-object payload, then write a faithful copy to a destination environment. The canonical use case: environment promotion — you build and verify a report in your preview sandbox (`acme.preview.workfront.com`) and want to land an equivalent report in production (`acme.my.workfront.com`).

Both source and destination use the v0.9.0 wire format. Every write call is `--data-urlencode 'updates={JSON}'` form-encoded; raw JSON request body is rejected by the v17.0 endpoint. The `definition` field on every UI-object row is a JSON OBJECT, not a stringified text-mode payload (see `01-report-object-shape.md` § 1.3 for the empirical correction to v0.8.0). All examples pin `v17.0` per `knowledge/api/01-api-fundamentals.md`.

The sanitiser walks the JSON-object `definition` trees recursively — it does NOT regex-scan stringified payloads the way the v0.8.0 walker did. Output has five buckets:

| Bucket | Meaning | Default action |
|---|---|---|
| `strip` | Definitely tenant-specific; drop without asking. | Auto-removed from `cleaned`. |
| `prompt` | Might be tenant-specific; intent matters. | Ask the admin per-item. |
| `parity_check` | `DE:<name>` custom-field references that need a destination-environment lookup. | Probe destination at Phase 5b. |
| `host_rewrite` | NEW in v0.9.0. Hard-coded `https://<source-host>/...` URLs inside `valueexpression` (or `image.case[].comparison.truetext`). | Ask auto-rewrite vs keep vs drop at Phase 5c. |
| `cleaned` | The bundle with `strip` items removed; `prompt` and `host_rewrite` items still present pending admin decision. | Carries into Phase 6. |

The whole flow is twelve phases. The hard rule that runs through every one: **never write to source.** Source credentials only hit the source host; destination credentials only hit the destination host. Every interactive step prints a banner naming the destination host + customer.

## Phase 1 — Source credentials and handshake

### Resolve the source environment

Run:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --source
```

This defaults to the currently active environment slug and lists the other registered environment folders (`~/wf-envs/`) so the admin can choose the source — typically the sandbox or preview environment where the report was built and verified, registered via `/wf-env-add` like any other.

The script prints the resolved source slug (e.g. `sandbox`). Activate it via `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-use.sh <slug>`, then use `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh ...` for reads. The wrapper sources `~/wf-envs/<slug>/.env`.

You never see the API key.

Handshake against source:
```bash
# After /wf-env-use <source-slug>:
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=customer:name'
```

Echo: `"Cloning from <source-customer-name> at <source-host>. Correct? [y/n]"`.

On 401/403 — ask the admin to verify the resolved slug's credentials. On `y` — proceed. No further work happens before this `y`.

## Phase 2 — Destination credentials and handshake

### Resolve the destination environment

Run:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-resolve.sh --dest
```

- Exit 0: prints the active slug. Extract `WF_HOST`, `WF_ENV_LABEL`, `WF_ENV_TYPE`, `WF_SCOPE_PORTFOLIO_ID`, and `WF_READ_ONLY` with `grep -E '^(WF_HOST|WF_ENV_LABEL|WF_ENV_TYPE|WF_SCOPE_PORTFOLIO_ID|WF_READ_ONLY)=' ~/wf-envs/<slug>/.env` — never read the full `.env`; it holds `WF_API_KEY`. Echo back for confirmation. Refuse if `WF_READ_ONLY="1"` (this recipe writes).
- Exit 2: tell the admin to register one via `/wf-env-add <slug>`, set the key, then `/wf-env-use <slug>`.

> If Phase 1 activated a source slug different from the destination, run `/wf-env-use <dest-slug>` before this resolve so the active pointer names the destination. Phase 3 switches back to the source for the pull.

Handshake against destination:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh /attask/api/v17.0/user/search \
  --data-urlencode '$$LIMIT=1' \
  --data-urlencode 'fields=customer:name'
```

Echo: `"Cloning to <dest-customer-name> at <dest-host>. Correct? [y/n]"`. Require `y`.

Then print the cross-environment confirmation banner — both hosts named, both customers named, and an explicit `y` required:

> "Cloning FROM **<src-customer-name>** AT `<src-host>` TO **<dest-customer-name>** AT `<dest-host>`. I will GET from source and POST to destination. I will NOT write to source. Type `y` to continue."

No further work happens before this second `y`. Both credential sets stay in conversation context only; neither is logged.

## Phase 3 — Source pull

Identify the source report by ID. If the admin gave a name instead of an ID, resolve via `/report/search?name=<name>&name_Mod=cicontains&fields=ID,name,uiObjCode&$$LIMIT=10` on the source. Then GET the report and each of its three referenced UI-objects (activate the source slug via `/wf-env-use <source-slug>` first if the destination is currently active):

```bash
# 1. The REPORT row — capture its three sibling-IDs
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  "/attask/api/v17.0/report/<sourceReportID>" \
  --data-urlencode 'fields=*,definition,filterID,groupByID,viewID,uiObjCode,categoryID,ownerID,homeGroupID' \
  > /tmp/clone-report.json

# 2-4. The three UI-objects (skip any whose ID is null on the REPORT row)
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  "/attask/api/v17.0/uift/<filterID>" \
  --data-urlencode 'fields=*,definition' \
  > /tmp/clone-uift.json
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  "/attask/api/v17.0/uigb/<groupByID>" \
  --data-urlencode 'fields=*,definition' \
  > /tmp/clone-uigb.json
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  "/attask/api/v17.0/uivw/<viewID>" \
  --data-urlencode 'fields=*,definition' \
  > /tmp/clone-uivw.json
```

Bundle the four responses into one in-memory document keyed by short name. Use `jq --slurpfile` so the four `.data` envelopes unwrap cleanly:

```bash
jq -n \
   --slurpfile r /tmp/clone-report.json \
   --slurpfile f /tmp/clone-uift.json \
   --slurpfile g /tmp/clone-uigb.json \
   --slurpfile v /tmp/clone-uivw.json \
   '{report: $r[0].data, uift: $f[0].data, uigb: $g[0].data, uivw: $v[0].data}' \
   > /tmp/clone-bundle.json
```

If `filterID` was null on the source REPORT row → omit the `uift` GET and pass `uift: null` (or drop the key) in the bundle. Same for `groupByID` / `uigb`. `viewID` is always present — a report cannot exist without a view (see `01-report-object-shape.md` § 4).

If the source `/report/<id>` GET returns 404, distinguish "doesn't exist" from "no read access" via a `/report/search?ID=<id>&fields=ID,name` lookup — if search returns nothing, the report doesn't exist; if search returns the row but GET 404s, it's an access issue. Surface the distinction to the admin.

## Phase 4 — Sanitisation (JSON-object walker)

Invoke the v0.9.0 sanitiser against the bundle. The script walks each row's JSON tree — including `uift.definition`, `uigb.definition.group[]`, `uivw.definition.column[]` and `uivw.definition.row[]` — and emits the 5-bucket report described at the top of this file.

```bash
python3 skills/workfront-reports/scripts/sanitize_clone.py --from-stdin \
   < /tmp/clone-bundle.json \
   > /tmp/clone-flags.json

# Save sanitization report to the exports folder
cp /tmp/clone-flags.json \
   ~/wf-envs/<dest-slug>/exports/$(date -u +%Y%m%dT%H%M%SZ)-report-clone-sanitization.json
```

Output shape (v0.9.0 — 5 buckets):

```json
{
  "strip": [
    {"key": "report.customerID", "value": "<source-customerID>"},
    {"key": "report.preferenceID", "value": "<source-preferenceID>"}
  ],
  "prompt": [
    {"key": "report.ownerID", "value": "<source-ownerID>",
     "reason": "tenant-local user ID — does not exist on destination"},
    {"key": "uift.definition.OR:1:assignedToID", "value": "<source-userID>",
     "reason": "hardcoded user GUID inside filter — may or may not exist on destination"}
  ],
  "parity_check": [
    {"field": "Project Tier", "uiObjCode": "PROJ",
     "source_form": "Project Detail Custom Form"},
    {"field": "Asset Tag", "uiObjCode": "PROJ"}
  ],
  "host_rewrite": [
    {"path": "uivw.definition.column[3].valueexpression",
     "url": "https://acme.preview.workfront.com/document/",
     "source_host": "acme.preview.workfront.com"}
  ],
  "cleaned": { "report": {...}, "uift": {...}, "uigb": {...}, "uivw": {...} }
}
```

### What the walker auto-strips

Removed from `cleaned`, recorded in `strip`. The admin is not asked.

- `customerID`, `preferenceID`, `securityRootID`, `appGlobalID` on any row — meaningless across environments. `preferenceID` carries chart/prompt orphaning (see `05-gotchas.md` #12).
- `entryDate`, `lastUpdateDate`, `modDate`, `lastUpdatedBy*`, `enteredBy*` on any row — set by the destination on POST anyway.
- The top-level `ID` on each of the four rows — POST mints new IDs on the destination.
- The REPORT row's `filterID`, `groupByID`, `viewID` — re-pointed in Phase 8 to the IDs returned by the destination UIFT/UIGB/UIVW POSTs.

### What the walker prompts

Recorded in `prompt`; values stay in `cleaned` pending the admin's per-item decision at Phase 5a.

- `ownerID` on the REPORT row — usually drop (the API key's owner becomes the new owner on POST), but the admin may want to set it to a known destination-environment user ID.
- `homeGroupID` on the REPORT row — usually drop. Some orgs group-scope reports; the admin decides.
- `categoryID` on the REPORT row — usually drop (rare to attach a custom form to a report row itself; see `05-gotchas.md` #2).
- Any other field on any row whose name ends in `ID` and isn't on the whitelist (`filterID`, `groupByID`, `viewID`, `uiObjCode`).
- **32-hex-character GUID values anywhere inside a `definition` object tree** — these are hard-coded references (a specific portfolio ID, a specific user ID, a specific custom-form ID). They will not resolve against the destination environment.
- **Hard-coded `YYYY-MM-DD` date values inside any `definition` value** — e.g., `plannedCompletionDate: "2026-04-01"`. These carry the source environment's timezone interpretation; see `05-gotchas.md` #6.

### What the walker collects for parity_check

Recorded in `parity_check`; values stay in `cleaned`. Probed against the destination at Phase 5b.

- Every `DE:<name>` reference inside a UIFT key — including `OR:N:DE:<name>` and `EXISTS:<token>:DE:<name>` keys, which the walker unwraps before extracting the name. See `06-filter-patterns.md` § 6, § 7, § 8.
- Every `DE:<name>` reference inside a UIVW column's `querysort` or an `aggregator.valuefield`.
- Every bare custom-field name inside a UIVW column's `valuefield` — the walker treats `column[].valuefield` as a DE: reference per the prefix asymmetry codified in `05-gotchas.md` #10 and `07-view-patterns.md` § 14.
- Every bare custom-field name inside a UIGB group's `valuefield` — same asymmetry (UIGB drops the `DE:` prefix; the walker normalises).
- Duplicates across UIFT keys, UIVW columns, UIVW querysort, UIVW aggregators and UIGB groups dedupe to one `parity_check` entry per field name.

### What the walker collects for host_rewrite (NEW in v0.9.0)

Recorded in `host_rewrite`. The walker scans every `valueexpression` string and every `image.case[].comparison.truetext` string for `https://[a-z][a-z0-9-]+(\.sb\d+)?\.(my|preview)\.workfront\.com/` patterns (production, sandbox, and preview hostnames) and for static asset paths like `/static/img/...`. Each match emits a `host_rewrite` entry with the dotted path, the matched URL, and the extracted hostname. The admin decides per-item at Phase 5c.

### What passes through unchanged

- `$$USER`, `$$TODAY`, `$$NOW`, `$$THISMONTH`, `$$EXISTSMOD`, `$$OBJCODE` and other `$$`-prefixed session/control tokens — tenant-neutral, never flagged. See `06-filter-patterns.md` § 4.
- All UIFT structural keys (`OR:N:`, `EXISTS:<token>:`) and operator suffixes (`*_Mod=eq`, `*_Mod=in`, etc.) — text-mode grammar is tenant-neutral; only specific values may be tenant-specific.
- All UIVW non-DE fields (`displayname`, `width`, `textmode`, `valueformat`, `link.*`, `styledef.*`).
- The REPORT row's `name`, `description`, `uiObjCode`, `reportType`, chart-related booleans. (The admin may want to rename — that's Phase 6 territory, not sanitisation.)

The script is pure Python and has unit tests in `tests/test_sanitize_clone.py` covering the strip / prompt / parity_check / host_rewrite / shape contracts.

## Phase 5 — Interactive review

Walk each non-empty bucket with the admin. Three sub-phases. Each printed prompt includes a banner naming the DESTINATION environment so the admin cannot lose track of which side is being written to.

### 5a. `prompt` items — per-entry ask

For each entry in `prompt`, ask one question:

> "Source `<key>` is `<value>`. Reason: `<reason>`. On destination, this would default to <default-behaviour>. Type `drop`, `keep`, or paste a destination-environment ID."

Common defaults the skill should advertise:

- `report.ownerID` → **drop** (let destination assign the report to the API key's owner).
- `report.categoryID` → **drop** (custom-form ID won't exist on destination).
- `report.homeGroupID` → **drop** unless the admin has a destination group ID in mind.
- 32-hex GUID inside a filter value → **drop** (clears the filter line) or paste a destination-environment ID to remap.
- Hard-coded date inside a filter value → **keep** (literal date), or convert to a `$$TODAY`-relative form per `06-filter-patterns.md` § 4 (the skill prints the suggested rewrite).

The skill applies each decision to `cleaned` in place, so the bundle that leaves Phase 5 is ready for Phase 6.

### 5b. `parity_check` items — `DE:` custom-field parity

For each `parity_check` entry, query the destination environment:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  /attask/api/v17.0/parameter/search \
  --data-urlencode 'name=<URL-encoded-name>' \
  --data-urlencode 'name_Mod=eq' \
  --data-urlencode 'fields=ID,name,parameterGroup:name' \
  --data-urlencode '$$LIMIT=10'
```

Three outcomes per `DE:<name>`:

- **0 matches → BLOCK.** Print:
  > "`DE:<name>` does not exist on **<dest-customer-name>**. Either create the custom field on the destination environment before re-running (with the same name and the same field type), or remove the column/filter line that references it. Type `edit` to revise, anything else to abort."

  Per `05-gotchas.md` #8 — the skill NEVER auto-strips a `DE:` reference. A missing custom field is almost always a real problem to solve, not a value to silently drop.
- **1 match → valid.** Print a green check; `cleaned` is unchanged.
- **Multiple matches → warn.** The same parameter name lives on more than one custom form on the destination. Surface the count and the parent-form names; ask the admin to confirm which form is the intended one. Cleaned payload still unchanged — the reference works at render time, but ambiguity at edit time is worth flagging.

### 5c. `host_rewrite` items — hard-coded URL leak (NEW in v0.9.0)

For each `host_rewrite` entry, ask:

> "`<path>` contains `<url>` (source host: `<source_host>`). Auto-rewrite to `https://<dest-host>/...` ? [auto / keep / drop]"

- **auto** (default) — substitute the source host with the destination host in place. The path stays; only the hostname is swapped. The skill prints the before/after snippet so the admin can sanity-check.
- **keep** — leave the URL as-is. Rare; only correct if the URL points at a third-party asset (Adobe shared service, etc.) that is the same across environments. Static-asset paths like `/static/img/r15/icons/...` are typically `keep` candidates because they resolve relatively on any tenant; the skill flags them but defaults to auto-rewrite anyway and lets the admin override.
- **drop** — strip the containing column or expression entirely. Use when the leaked link is not meaningful on the destination (e.g., a "View source asset" link that no longer makes sense outside the source environment).

Per `05-gotchas.md` #11 — this bucket exists because the Client D clone bundles (`OPTASK-rush-L-uivw.json`, `OPTASK-mktg-retail-uivw.json`, `DOCU-proofs-retail-uivw.json`, `PRFAPL-completed-L-uivw.json`) all embed `https://client-d.my.workfront.com/...` literals inside `valueexpression`. Without `host_rewrite`, clicking the cloned link opens the source tenant — in the promotion flow, that sends prod report viewers to your preview sandbox.

After 5c, the in-place edits land back in `cleaned`. The bundle is now ready for optional mutation.

## Phase 6 — Optional mutation

If the admin's NL request includes changes ("clone this report but show closed projects instead of active", or "same report but grouped by portfolio instead of program"), apply the diff on top of the `cleaned` payload — same NL-to-JSON interview pass as `02-create-from-scratch-recipe.md` § Phase B, scoped to the slots the admin asked to change.

The mutation phase never widens scope: a filter-only change does not touch `uivw.definition.column[]`. A column-only change does not touch `uift.definition`. The skill prints the before/after for each affected `definition` block so the admin can sanity-check the diff against the cleaned source.

If the admin did not request any change, skip this phase.

## Phase 7 — Destination schema discovery

Run the four-call `/metadata` burst against the destination host plus the target-object metadata for the source REPORT row's `uiObjCode` (which is preserved across environments — PROJ stays PROJ). Documented in `04-runtime-schema-discovery.md`. The cache key is host-hashed so source and destination caches coexist without interfering.

If the destination's `/report/metadata` reports a field name discrepancy against the source row (rare, but the case where Workfront has renamed or aliased a field between source and destination environment versions exists), the skill renames the field on the cleaned REPORT row and prints a one-line warning. If a field name from the cleaned payload doesn't appear on either side of the destination's metadata, drop it and print a one-line warning.

## Phase 8 — Compose destination payloads

Same four-call structure as `02-create-from-scratch-recipe.md` § Phase C. The four bodies come from `cleaned`. Set:

- `uiObjCode` to the source value on REPORT, UIFT, UIGB, UIVW (must match across all four — see `05-gotchas.md` #1).
- `name` on each sibling to `"<dest-report-name> — filter"`, `"<dest-report-name> — group"`, `"<dest-report-name> — view"` per the naming convention from `02-create-from-scratch-recipe.md` § Phase C.
- `filterID` / `groupByID` / `viewID` on the REPORT body to placeholder values; they get patched to real IDs in Phase 11 after the three sibling POSTs land.

Print all four payloads with a diff against the source bundle, so the admin can verify the sanitiser's choices and the destination-environment naming before the gate.

## Phase 9 — Pre-flight validation against destination

Run the pre-flight validator against the four composed payloads. The validator catches field-existence errors against the destination's `/<uiObjCode>/metadata` cache — the PROJ-vs-TMPL trap from `05-gotchas.md` #9 — and re-runs DE: parity as a belt-and-braces check on top of Phase 5b. See `08-pre-flight-validation.md` for the algorithm.

```bash
jq -n \
   --arg uift   "$(cat /tmp/dest-uift-payload.json)" \
   --arg uigb   "$(cat /tmp/dest-uigb-payload.json)" \
   --arg uivw   "$(cat /tmp/dest-uivw-payload.json)" \
   --arg report "$(cat /tmp/dest-report-payload.json)" \
   '{uift: ($uift|fromjson), uigb: ($uigb|fromjson), uivw: ($uivw|fromjson), report: ($report|fromjson)}' \
  | (set -a; source ~/wf-envs/<dest-slug>/.env; set +a; \
     python3 ${CLAUDE_PLUGIN_ROOT}/skills/workfront-reports/scripts/pre_flight_validator.py \
       --from-stdin) \
  > /tmp/preflight.json
```

- **`valid: false`** — print errors with suggestions; admin types `edit` to revisit Phase 5 or Phase 6. No bytes write.
- **`valid: true` with warnings** — surface and proceed to Phase 10.
- **`valid: true` clean** — proceed to Phase 10.

Pre-flight reads only from the cached metadata plus, at most, a single batched `/parameter/search` and `/customform/search` GET against the destination. It does not write.

## Phase 10 — Single `apply` gate

Banner — destination-named, with the cross-environment guarantee re-stated:

> "Writing 2-4 new rows to **<dest-customer-name>** at **<dest-host>**: 1× UIFT, 0-1× UIGB, 1× UIVW, then 1× REPORT referencing those IDs. Pre-flight: **GREEN** (0 errors, N warnings). Source (**<src-customer-name>** at `<src-host>`) will NOT be modified. Type `apply` to proceed, `edit` to revisit sanitisation choices, or anything else to abort."

Only the literal string `apply` proceeds. `y`, `yes`, `apply now`, blank-Enter — none of those count. `edit` returns to Phase 5 with prior answers prefilled. Anything else aborts.

## Phase 11 — Write to destination

### Switch active environment to destination

Before the write sequence, run:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-use.sh <dest-slug>
```

You'll see the wf-env-use confirmation line — verify it matches the destination slug you resolved in `### Resolve the destination environment`. From this point until the end of the recipe, every `wf-env-curl.sh` invocation hits the destination environment.

Same 2/3/4-call POST sequence as `02-create-from-scratch-recipe.md` § Phase F. Each call uses `--data-urlencode 'updates=<json>'`; raw JSON body is rejected by the v17.0 endpoint.

If the destination is prod, prepend `WF_ENV_WRITE_ACK=1` before each write call after the admin types `yes` at the prod-write-ack prompt (see SKILL.md safety baseline).

```bash
# 1. UIFT (filter) — always written, even when source filter was empty {}
FILTER_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/uift \
  --data-urlencode "updates=$(cat /tmp/dest-uift-payload.json)" \
  | jq -r '.data.ID')
echo "[1/4] UIFT created on dest: $FILTER_ID"

# 2. UIGB (groupBy) — SKIP this entire block if source had groupByID:null
GROUP_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/uigb \
  --data-urlencode "updates=$(cat /tmp/dest-uigb-payload.json)" \
  | jq -r '.data.ID')
echo "[2/4] UIGB created on dest: $GROUP_ID"

# 3. UIVW (view)
VIEW_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/uivw \
  --data-urlencode "updates=$(cat /tmp/dest-uivw-payload.json)" \
  | jq -r '.data.ID')
echo "[3/4] UIVW created on dest: $VIEW_ID"

# 4. REPORT — patch the three sibling IDs into the payload first, then POST.
jq --arg fid "$FILTER_ID" --arg gid "$GROUP_ID" --arg vid "$VIEW_ID" \
   '.filterID=$fid | .groupByID=$gid | .viewID=$vid' \
   /tmp/dest-report-payload.json \
   > /tmp/dest-report-payload-resolved.json
REPORT_ID=$(WF_ENV_WRITE_ACK=1 bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  -X POST /attask/api/v17.0/report \
  --data-urlencode "updates=$(cat /tmp/dest-report-payload-resolved.json)" \
  | jq -r '.data.ID')
echo "[4/4] REPORT created on dest: $REPORT_ID"
```

If the source had no UIGB → omit step 2 and pass `null` for `groupByID` in step 4's jq patch (`.groupByID=null` rather than `.groupByID=$gid`).

If any of the POSTs fails mid-sequence, follow the error-handling table in `02-create-from-scratch-recipe.md` § Error handling — print DELETE curls for whatever was already created on the destination, then stop. Source is untouched by definition.

## Phase 12 — Smoke-test + URLs

Immediately after the REPORT POST returns, GET the report back to detect silent re-resolution per `05-gotchas.md` #5:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh \
  "/attask/api/v17.0/report/$REPORT_ID" \
  --data-urlencode 'fields=*,definition,filterID,groupByID,viewID' \
  | tee ~/wf-envs/<dest-slug>/exports/$(date -u +%Y%m%dT%H%M%SZ)-report-clone-smoke.json \
  | python3 -m json.tool
```

Compare the response's `filterID` / `groupByID` / `viewID` against the IDs captured in Phase 11 steps 1-3. If any differ, Workfront silently re-resolved the report to point at a pre-existing destination-environment UI-object whose `definition` matches byte-for-byte. The cloned report renders correctly, but the UI-objects the skill POSTed are now orphaned in the destination environment. Print the diff plus DELETE curls for the orphans so the admin has manual cleanup in terminal scrollback.

Then print both URL forms per `01-report-object-shape.md` § 7 and `05-gotchas.md` #4:

```
Report cloned.
  https://<dest-host>/report/<REPORT_ID>
  https://<dest-host>/report/<REPORT_ID>/view
```

The bare URL opens the report's editor; the `/view` suffix renders the report immediately. The skill prints both.

## Cross-environment safety summary

The whole flow exists to make these rules non-negotiable:

1. **Source credentials only ever hit source host.** Never appear in a POST / PUT / DELETE URL.
2. **Destination credentials only ever hit destination host.** Never appear in a source-host GET.
3. **Every interactive step prints a banner naming the destination host + customer.** No phase forgets which tenant is being written to.
4. **`customerID`, `preferenceID`, `securityRootID` on the source row are AUTO-STRIPPED.** Never carried over; recorded in `strip`.
5. **`ownerID`, `categoryID`, `homeGroupID` are PROMPTED.** Not auto-stripped — admin intent matters.
6. **`DE:` references are NEVER auto-stripped.** Missing custom field on destination is almost always a real problem to solve; recorded in `parity_check` and probed at Phase 5b.
7. **Hard-coded URLs in `valueexpression` are flagged for review.** NEW in v0.9.0; recorded in `host_rewrite` and resolved at Phase 5c per `05-gotchas.md` #11.
8. **`apply` is the only word that triggers writes.** Phase 10 banner reminds the admin that source will not be modified.

## Cross-references

- The JSON-object walker behavior detail and per-bucket logic → `skills/workfront-reports/scripts/sanitize_clone.py` docstring and `tests/test_sanitize_clone.py`.
- The `DE:` prefix asymmetry across UIFT / UIGB / UIVW that the walker normalises → `05-gotchas.md` #10 and `07-view-patterns.md` § 14.
- The custom-form parity rule the skill enforces at Phase 5b → `05-gotchas.md` #8.
- The host-URL leakage gotcha that motivated the `host_rewrite` bucket → `05-gotchas.md` #11.
- The preferenceID orphaning that auto-strips chart and prompt state → `05-gotchas.md` #12.
- Filter syntax — `OR:N:` groups, `EXISTS:<token>:` blocks, `$$`-prefixed session tokens, `_Mod` operators, multi-value TAB separator — that the walker recognises → `06-filter-patterns.md`.
- View and group syntax — `column[].valuefield`, `column[].querysort`, `column[].aggregator.valuefield`, `column[].valueexpression`, `column[].image.case[]`, `group[].valuefield` — that the walker traverses → `07-view-patterns.md`.
- Pre-flight algorithm — field-existence checks, DE: probe, locale-shift warnings, the `--force` override → `08-pre-flight-validation.md`.
- The four-call write sequence Phases 7-12 essentially re-apply against the destination → `02-create-from-scratch-recipe.md` § Phase C-H.
- The REPORT / UIFT / UIGB / UIVW field map and the `definition`-is-a-JSON-object correction → `01-report-object-shape.md`.
- The `/metadata` burst and the host-hashed cache → `04-runtime-schema-discovery.md`.
- Auth headers, the `apiKey:` vs `sessionID:` choice, `$$HOST` resolution → `workfront-api`.
- Text-mode authoring (the in-product Text Mode tab is the human-editable surface; the wire format is always a JSON object) → `workfront-textmode`.
