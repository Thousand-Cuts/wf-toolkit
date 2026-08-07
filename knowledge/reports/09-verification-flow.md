# 09 — Verification Flow (`[wf-reports-verify]`)

The reports skill can verify its own behaviour against a real Workfront environment before reporting a documentation divergence. This document explains the `[wf-reports-verify]` flow: the prefix, the audit log, the revert path, and the self-learning loop that fold live findings back into the per-environment pseudo-fields whitelist.

This file mirrors `knowledge/api/13-local-verification.md` for the reports skill. Where they overlap (credentials store, audit dir, revert script), the API doc is the canonical source; this file describes only what is reports-specific.

## § 1. Why this exists

v0.9.x's empirical-discovery loop (live test → hand-written divergence report) works but takes a dedicated brainstorm cycle per finding. Several real classes of finding — pseudo-fields missing from `/metadata`, sharecol/HTML sanitizer rules, undocumented field-relation accessibility — recur across environments. v0.10.0 formalises the loop: every report written via the verify flow is prefix-tagged, audit-logged, and (when `--force` was used) feeds the per-environment whitelist automatically.

## § 1.5 Scope of this flow

The `[wf-reports-verify]` flow is **for verifying the skill's documented behaviour only**. It exists to confirm a suspected divergence against your own Workfront sandbox before reporting it (the divergence policy — trust observed behaviour, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues, never edit the installed plugin's files — lives in `00-rubric-and-workflow.md` § "Closing phase"). It uses the existing `wf-curl.sh` wrapper (from `skills/workfront-api/scripts/`) and the active credential from the shared environment store (`~/wf-envs/<slug>/.env`, provisioned via `/wf-env-add`).

It is **not** for real reports work. Day-to-day reports work in your instance (NL-create, modify, clone-and-adapt destination) goes through the separate `wf-env-curl.sh` wrapper (added in v0.18.0+). Both wrappers read the same store (`~/wf-envs/`, audit files under `~/wf-envs/<slug>/audit/`) but serve different purposes:

| Concern | Verify flow (this file) | Working flow |
|---|---|---|
| Wrapper | `skills/workfront-api/scripts/wf-curl.sh` | `skills/_shared/scripts/wf-env-curl.sh` |
| Prefix guard | `[wf-reports-verify]` enforced on creates | None (writes don't need a sentinel prefix) |
| Prod-write-ack | `WF_VERIFY_WRITE_ACK` required when `WF_ENV_TYPE=prod` | `WF_ENV_WRITE_ACK` required when `WF_ENV_TYPE=prod` |
| Purpose | Verify documented behaviour before filing a divergence issue | Real reports work in your instance |

The rest of this file describes the verify flow.

## § 2. One-time setup

```bash
bash skills/workfront-reports/scripts/wf-reports-verify-setup.sh
```

Writes `~/wf-envs/reports-verify.env`:

```bash
WF_VERIFY_PREFIX="[wf-reports-verify]"
WF_VERIFY_OBJCODES="report,uift,uigb,uivw"
```

Idempotent — re-running overwrites with the same content. Credentials themselves are reused from the shared environment store (`/wf-env-add`, `~/wf-envs/<slug>/.env`). The reports skill never asks for a separate API key.

## § 3. The `[wf-reports-verify]` prefix

Every report created via the verify flow has `name=[wf-reports-verify] <description>` set in the REPORT POST body. `wf-curl.sh` reads `WF_VERIFY_PREFIX` and enforces the prefix at the wrapper level — a create without the prefix is refused with a die message. This guarantees every reports-flow throwaway is unambiguously labeled.

The UIFT/UIGB/UIVW objects don't carry a name (they're sub-objects), so the prefix only attaches to the REPORT row. Cleanup uses the prefix on REPORT plus the `WF_VERIFY_OBJCODES` list to sweep the dependent objects: `wf-cleanup.sh` finds reports by prefix, then walks REPORT → filterID/groupByID/viewID to enumerate the sub-rows for deletion.

## § 4. Audit log and revert

Every UIFT/UIGB/UIVW/REPORT POST goes through `wf-curl.sh`. For creates (POST with no ID in the path), the wrapper requires the prefix but does NOT write an audit file — there's no pre-state to capture. For mutations (PUT, DELETE), the wrapper writes a pre-state JSON to `~/wf-envs/<slug>/audit/<UTC>-<method>-<objcode>-<id>.json` before sending the request.

To roll back: `wf-revert.sh <audit-file>` reverses the captured change. For a create that needs to be undone, use `wf-cleanup.sh` (which knows to follow `filterID`/`groupByID`/`viewID` to delete the UI-objects in the right order).

v0.10.0 audit-logs the four creates only when a follow-up PUT/DELETE happens (matching v0.9.x behavior). The MODIFY flow's GET-before-PUT continues to print pre-state to scrollback as the manual rollback path. v0.11.0+ may extend the wrapper to write pre-state on creates too, but that's out of scope here.

## § 5. Pre-flight `--force` + auto-capture

The full live-test loop:

```bash
# 1. Pre-flight composes the bundle (Phase D of the recipe), then runs.
#    WF_HOST / WF_API_KEY come from the recipe's `set -a; source .env` step —
#    the validator reads them from the environment, never from argv:
python3 skills/workfront-reports/scripts/pre_flight_validator.py \
    --from-stdin \
    < /tmp/bundle.json \
    > /tmp/preflight.json

# 2. If errors[], you can either edit OR override:
python3 skills/workfront-reports/scripts/pre_flight_validator.py \
    --from-stdin --force \
    < /tmp/bundle.json \
    > /tmp/preflight-forced.json
# /tmp/preflight-forced.json now has valid:true, errors:[], and the
# original errors as warnings[] with forced:true.

# 3. apply gate, then write sequence runs via wf-curl.sh.

# 4. ON REPORT-POST HTTP 200 (only): SKILL.md invokes the validator a
#    SECOND time to persist the forced findings:
python3 skills/workfront-reports/scripts/pre_flight_validator.py \
    --host "$WF_HOST" \
    --learn-objcode "$UIOBJCODE" \
    --learn-from-blocked /tmp/preflight-forced.json
# The forced warnings get written to
# ~/.cache/wf-toolkit/reports-pseudo-fields-<host-hash>.json
# with learned_via:"auto-force" + the session ID.
```

The user types `--force` once (when the recipe asks). The SKILL.md orchestrator handles the second invocation automatically — "automatic" meaning "no additional typing required," not "happens without user authorization." The whitelist write is gated on REPORT-POST HTTP 200; if any earlier call in the 4-call sequence fails, no learning happens.

## § 6. Manual `--learn` and `--forget`

When the user knows up-front a field is environment-local and doesn't want to go through the force-write loop:

```bash
pre_flight_validator.py --host "$WF_HOST" \
    --learn OPTASK:customStateEquatesWith:uift.definition
```

Adds one entry without writing anything to the destination environment. Useful for documenting a known environment-local pseudo-field after a separate discovery.

To remove entries:

```bash
pre_flight_validator.py --host "$WF_HOST" --forget OPTASK:customStateEquatesWith
pre_flight_validator.py --host "$WF_HOST" --forget-all
```

`--forget` removes one (uiObjCode, fieldname) entry; `--forget-all` deletes the environment's whole whitelist file. Use `--forget-all` as the recovery path when the whitelist gets corrupted (the validator emits a warning when it loads a corrupt file and treats it as empty).

## § 7. Sharing with `workfront-api`

| Shared | Owned by `workfront-api` | Owned by `workfront-reports` |
|---|---|---|
| `~/wf-envs/<slug>/.env` credentials | yes | reused |
| `~/wf-envs/<slug>/audit/` | yes | reused |
| `wf-curl.sh` script | yes | reused (with `WF_VERIFY_PREFIX` env var override) |
| `wf-cleanup.sh` script | yes | reused (with `WF_VERIFY_PREFIX` + `WF_VERIFY_OBJCODES` env var overrides) |
| `wf-revert.sh` script | yes | reused as-is |
| `reports-verify.env` | — | owned (one-time setup) |
| `reports-pseudo-fields-<host-hash>.json` whitelist | — | owned |
| Knowledge files (08-pre-flight-validation, 09-verification-flow) | — | owned |

The two flows do not conflict at runtime: the `[wf-api-verify]` and `[wf-reports-verify]` prefixes are disjoint, and `wf-cleanup.sh` reads `WF_VERIFY_OBJCODES` so each skill's invocation only sweeps its own object set. A workfront-api session and a workfront-reports session can both leave residue in the same environment; each skill's cleanup only removes its own.

## § 8. Cross-references

- The `workfront-api` analog of this flow → `knowledge/api/13-local-verification.md`.
- The hard-coded `PSEUDO_FIELDS` allowlist that the per-environment whitelist overlays → `08-pre-flight-validation.md` § 4d.
- The recipe integration point (pre-flight runs at Phase D of both create and modify) → `02-create-from-scratch-recipe.md` § Phase D.
- The 4-call write rubric (UIFT → UIGB → UIVW → REPORT) and which calls audit-log → `00-rubric-and-workflow.md`.
- The schema cache that the validator consults before any whitelist lookup → `04-runtime-schema-discovery.md`.
- The `wf-revert.sh` semantics (audit-file → reverse-action mapping) → `knowledge/api/13-local-verification.md` § "Safety model" (Guard 3 — audit log on mutations) and § "Reverts: `wf-revert.sh`".
