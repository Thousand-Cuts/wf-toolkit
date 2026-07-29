---
name: workfront-custom-forms
description: Use when a Workfront admin needs to design, audit, or migrate Workfront custom forms (Category objects) and their fields (Parameter objects) — e.g. "create a custom form for projects", "add a 50-option dropdown", "show field X when Y is Z", "where is the Vendor field used?", "which projects have form X attached?", "clone this form from sandbox into prod", "duplicate this form". Sibling to workfront-calc-fields — that skill owns the calculation body on calculated fields; this one owns the structural envelope: form, fields, options, attachment, display logic (show/hide rules), audit, and same- or cross-environment clone. Handles dropdowns of 200+ options and display-logic (cascade-rule) authoring. Triggers: "custom form", "Category object", "add a field", "form audit", "clone/duplicate this form", "DE: field", "display logic", "show/hide rule", "show X when Y". Distinct from workfront-calc-fields (calc body syntax), workfront-api (parameterValues reads), workfront-textmode (report views over forms). Out of scope: External Lookup authoring at create-time, sharing at create-time, bulk attach to records, dataType/displayType-change migrations (data-destructive — hard-blocked). Verified enum/objCode details live in `knowledge/custom-forms/`.
---

# Workfront Custom Forms

Design, audit, and migrate Workfront custom forms via the REST API. Five flows:

1. **NL-create** — author a form from a natural-language description (form name + target objCode + per-field details + inline display logic). NL cascade-rule parser handles "show X when Y is Z" / "hide X when Y is Z" / "show the rest of the form when Y is Z" / multi-match AND / otherwise-show patterns in the same brief as the field list.
2. **Add field / modify display logic on existing form** — given `categoryID`, either append a parameter via the field-add sub-flow or add/edit/remove a cascade rule via the cascade-rule sub-flow. Both share the GET-modify-PUT pattern because `categoryParameters` and `categoryCascadeRules` are both collection-REPLACE on PUT.
3. **Audit a single form** — print structure (parameters, types, options, attachment count, **display rules** in prose form).
4. **Audit usage across tenant** — "where is form X attached?" (`/<obj>/search?categories:ID=<id>`) and "which forms have field Y?" (single `GET /<objcode>/metadata` reading `data.custom`, with fallback to the legacy walk when a field exists but isn't currently attached to any record).
5. **Clone-and-adapt** — cross-environment lift-and-shift (e.g. sandbox → prod promotion) with ID sanitisation, source→dest cascade-rule remap, and auto-skip-with-report for rules orphaned by sanitization-side parameter drops. Same-environment duplicates run the same sequence with identity-remap simplifications — the planned `/copy` REST fast-path was retracted at smoke gate (2026-05-22): `copy` is in Category's `operations` metadata but isn't actually reachable via REST in v17.0.

Read `knowledge/custom-forms/00-rubric-and-workflow.md` before starting any run.

## Scope

- **In scope:** Five flows above. Bulk-options input for DROP/RADIO/CHECKBOX parameters (paste / CSV / clone-from-existing / generate-from-query, with bulk-POST tunneling). Runtime schema discovery via `/<object>/metadata`. Cross-environment sanitisation of categoryID / parameterID / parameterGroupID references inside displayLogic.
- **Out of scope:** Calculation body authoring (defer to `workfront-calc-fields`). External Lookup authoring (read-through only on clone; defer to `workfront-api`). AccessRule / sharing at create-time (v2). Bulk attach to N existing records (script per-record updates via the API). parameterType-change migrations (data-destructive — hard-blocked). Adobe Workfront Migrator workflows. API versions other than `v17.0`.

## Safety / Credentials

Every API call to your Workfront instance goes through `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh`. The wrapper sources `~/wf-envs/<active>/.env` for the host + key — no key in argv, no key in chat. To register an environment, run one terminal command: `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-setup.sh <slug>` (it prompts for metadata + the API key with hidden input and activates the environment). See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/env-credentials-and-safety.md`.

**Read-only environment folders** (`WF_READ_ONLY=1` in .env) refuse writes. NL-create and add-field flows refuse to start against a read-only folder. The audit flows (Flow 4: "where is form X attached?", "which forms have field Y?") work fine against read-only folders since they're GET-only.

**Prod-destination writes require explicit acknowledgement.** When the active environment is `WF_ENV_TYPE=prod`, the wrapper refuses every write (exit 3) until `WF_ENV_WRITE_ACK=1` is set per call. Before the first write (form POST, parameter POST, bulk-options POST, or category PUT for the link step), surface the prod-write warning verbatim, get a typed `yes`, then prepend `WF_ENV_WRITE_ACK=1` to every wrapper invocation in that batch. Don't re-ack within the same batch.

**The `[wf-api-verify]` prefix flow is separate.** It targets your own verification sandbox for sanity-checking observed-vs-documented behavior — uses `wf-curl.sh` (the verification wrapper from `skills/workfront-api/scripts/`). Don't conflate it with the environment-store flow. See `knowledge/api/13-local-verification.md` for the details.

If live behavior diverges from what this skill documents, trust the observed behavior for the task at hand and treat the divergence as possibly environment-specific (Workfront version, package, or configuration); if it looks globally true, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues with the endpoint, API version, date, and observed-vs-documented behavior — never edit the installed plugin's files.

## Safety baseline

- **`[wf-api-verify]` prefix is for verification flows only** (toolkit dev sanity-checking against your own sandbox, not your registered environments). Enforced by `wf-curl.sh` and swept by `wf-cleanup.sh`. See `knowledge/api/13-local-verification.md`. Environment writes go through `wf-env-curl.sh` and don't use this prefix.
- **One `apply` gate per run.** Per the toolkit convention. The admin types `apply` once to authorise the multi-call POST sequence. Prod destinations also require a separate typed `yes` for the prod-write-ack (see § Safety / Credentials).
- **Hard-block on parameterType changes.** Changing a parameter's type destroys existing values across every record. The skill refuses the write and recommends create-new + scripted value migration.
- **Never write skill metadata into user-facing fields.** `Parameter.description`, `Category.description`, and `ParameterGroup.description` are end-user-facing — they render as "Instructions" / form-header text to every user filling out the form. Do **not** write action-item IDs, dates, audit notes, or any agent-generated metadata into these fields. Default these to empty on POST/PUT unless the admin explicitly asked for user-facing helper text. See `knowledge/custom-forms/09-gotchas.md` § 21.
- **Pin `v17.0`** per repo convention.

## Defer to peer skills

- **Authentication, `$$HOST`, API version pinning, pagination, error semantics, External Lookup reads, `parameterValues` wildcard:** `workfront-api`
- **Calculation body inside `parameterType=COMP` parameters:** `workfront-calc-fields`
- **Audit output rendered as a Workfront report:** `workfront-textmode`

## Knowledge files

Read in this order on first run; re-read just the relevant file on subsequent runs:

- `../../knowledge/custom-forms/00-rubric-and-workflow.md` — when to use, interview script, decision tree. **Read when:** any custom-forms task.
- `../../knowledge/custom-forms/01-object-model.md` — Category / Parameter / ParameterGroup / ParameterOption / CategoryParameter; relationship graph. **Read when:** first run, or any "how do these fit together?" question.
- `../../knowledge/custom-forms/02-parameter-types.md` — per-type required fields, dataFormat enums, render behaviour. **Read when:** authoring a new field.
- `../../knowledge/custom-forms/03-create-form-recipe.md` — Flow 1 NL-create, including bulk-options handling and the 4-stage POST sequence. **Read when:** creating a new form.
- `../../knowledge/custom-forms/04-add-field-to-existing-form.md` — Flow 2. **Read when:** adding to an existing form.
- `../../knowledge/custom-forms/05-audit-recipes.md` — Flows 3 and 4. The "where is form X attached?" / "which forms have field Y?" playbooks. **Read when:** any audit-style question.
- `../../knowledge/custom-forms/06-clone-and-adapt-recipe.md` — Flow 5. Cross-environment sanitisation, displayLogic ID remap, calc-body parity check. **Read when:** the admin says "clone" / "lift and shift" / "promote" / names a source environment.
- `../../knowledge/custom-forms/07-display-logic.md` — the under-documented displayLogic JSON shape, captured empirically. **Read when:** authoring or migrating display logic.
- `../../knowledge/custom-forms/08-runtime-schema-discovery.md` — 5-GET `/metadata` flow + cache. **Read when:** before any write to a tenant the skill hasn't seen this session.
- `../../knowledge/custom-forms/09-gotchas.md` — rename aliasing, parameterType-change data destruction, per-record attachment lifecycle, value-vs-label rename semantics. **Read when:** any unexpected outcome or to pre-empt one.

## Helper scripts

Under `scripts/`:

- `option_list_parser.py` — parses dropdown option lists in 4 input modes (paste / CSV / TSV / comma / label=value) with autodetection. Output feeds the bulk-POST body.
- `form_sanitizer.py` — pure walker that flags environment-specific identifiers in a source form payload (drop / remap / review / parity-check actions).
- `schema_cache.py` — host-hashed 24h schema cache for runtime metadata.

All three are pytest-covered. See `tests/test_option_list_parser.py`, `test_form_sanitizer.py`, `test_custom_forms_schema_cache.py`.

## Workflow at a glance

```
Admin question
    ├── "create a form for projects to track X"     → Flow 1 → 03-create-form-recipe.md
    ├── "add a field to form Y"                     → Flow 2 → 04-add-field-to-existing-form.md
    ├── "what's on form Y?" / "audit this form"     → Flow 3 → 05-audit-recipes.md
    ├── "where is form Y attached?"                 → Flow 4a → 05-audit-recipes.md
    ├── "which forms have field Z?"                 → Flow 4b → 05-audit-recipes.md
    └── "clone form X from sandbox into prod"       → Flow 5 → 06-clone-and-adapt-recipe.md

Each create / modify / clone flow:
    1. Resolve active environment via wf-env-resolve.sh --dest; refuse if WF_READ_ONLY=1
    2. Schema discovery via wf-env-curl.sh /<obj>/metadata (cached if recent)
    3. Resolve inputs from natural-language
    4. Build payloads, show, single `apply` confirm
    5. If WF_ENV_TYPE=prod: surface prod-write warning, get typed `yes`, then prepend WF_ENV_WRITE_ACK=1 to every write
    6. Write the POST sequence via wf-env-curl.sh (Category → ParameterGroup → Parameter → ParameterOption → CategoryParameter)
    7. Print URL + the in-product builder URL
    8. Offer follow-up: attach to existing records via scripted per-record updates
```

Out-of-scope asks (calc body authoring, bulk record attachment, AccessRule edits, etc.) get routed with a one-line explanation. Refuse rather than drift.
