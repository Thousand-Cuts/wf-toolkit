# 00 — Rubric and Workflow

## When to use this skill

- "Create a custom form for projects (or any objCode) that captures fields X, Y, Z."
- "Add a new field to this form."
- "What's on form X?" / "Audit this form."
- "Where is form X attached?" / "Which forms have field Y?"
- "Clone a form between environments (e.g. promote a sandbox-verified form to prod)."

Do **not** use when:

- Authoring the calculation body on a `displayType=CALC` field — route to `workfront-calc-fields`. The formula lives on the `CategoryParameter.customExpression` field, not on the Parameter itself.
- Authoring External Lookups — defer to `workfront-api` `knowledge/api/12-external-lookup-fields.md` (v1 reads through on clone but does not author).
- Bulk attaching a freshly-created form to existing records — out of scope; script per-record `objectCategories` updates via the API.
- Modifying AccessRules / sharing — out of scope v1.

## Decision tree

```
Admin intent
  ├── "create a form" / "new custom form"        → Flow 1 (NL-create)
  ├── "add a field" / "extend this form"          → Flow 2 (add field)
  ├── "audit this form" / "show me the structure" → Flow 3 (single-form audit)
  ├── "where is form X used?"                     → Flow 4a (usage by form)
  ├── "which forms have field Y?"                 → Flow 4b (usage by field)
  └── "clone this form"                           → Flow 5 (cross-environment clone)
```

## Interview script — Flow 1 NL-create

Collect (ask only what's missing):

| Input | Notes |
|---|---|
| Form name | Short, descriptive |
| Target objCode | PROJ, TASK, OPTASK, USER, GROUP, PORT, DOCU. NOT supported: PROG, TMPL, TTSK (Phase B-verified — Workfront rejects with `invalid value <X> for enum CategoryObjTypesEnum`). Refuse the flow upfront if the admin asks for one of those three. |
| Description (opt) | Free text |
| Field list | Per-field: `label` (UI string), `dataType` (TEXT/NMBR/DATE/CURC/RICH/WIDGET), `displayType` (TEXT/SLCT/CHCK/RDIO/TXTA/MULT/TYAH/RICH/CALC/WIDGET/DTXT), options (for SLCT/CHCK/RDIO), required, description. See `02-parameter-types`. |
| Parameter groups (opt) | Sections within the form |
| Display logic (opt) | **REST-accessible since v0.25.0 (Phase B-3).** Author via the `categoryCascadeRules` collection on Category. matchType enum is binary (`EXIST` / `NOTEXIST`). See `07-display-logic`. |

For dropdowns with many options, route to bulk-options input modes in `03-create-form-recipe`.

## Safety baseline

- **Credentials** in `~/wf-envs/<slug>/.env` at mode 600 (set via `wf-env-setkey.sh` in your terminal). Every API call to your Workfront instance goes through `bash ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/wf-env-curl.sh` — no key in argv, no key in chat. See `skills/workfront-custom-forms/SKILL.md` § Safety / Credentials.
- **Read-only folders** (`WF_READ_ONLY=1`) refuse writes. NL-create + add-field flows refuse to start; audit flows (GET-only) work.
- **Prod destinations** require `WF_ENV_WRITE_ACK=1` per wrapper write call (after the admin types `yes` once per session).
- **`[wf-api-verify]` prefix is for verification flows only** (sanity-checking the skill's documented behavior against your own sandbox). Enforced by `wf-curl.sh`; **`wf_verify_` snake_case prefix on Parameter** since Workfront rejects `[` in Parameter `name`/`label`. See `09-gotchas` and `knowledge/api/13-local-verification.md`. Environment writes (through `wf-env-curl.sh`) do NOT use this prefix.
- One `apply` gate per multi-call sequence
- `dataType` / `displayType` changes are hard-blocked (data-destructive — see `09-gotchas` #2)
- `ParameterOption.value` renames are hard-blocked (orphans records — see `09-gotchas` #9)
- **Refuse upfront** if the admin requests a Category against `PROG`, `TMPL`, or `TTSK` objCodes. `CategoryObjTypesEnum` rejects all three (Phase B finding, 2026-05-22). Surface: "Custom forms are not supported on Programs / Templates / Template Tasks in v17.0. The valid objCodes are PROJ, TASK, OPTASK, USER, GROUP, PORT, DOCU."
- **`(WIDGET, WIDGET)` is deprecated** in v17.0. Refuse the combination and surface the 15 valid replacements (see `02-parameter-types` displayType enum) before re-prompting the admin. Phase B-1 will verify which replacements actually work in a live sandbox.
- Pin `v17.0`

## Closing phase: divergence policy

If live behavior diverges from what this skill documents: trust the observed behavior for the task at hand, and treat the divergence as possibly environment-specific (Workfront version, package, or configuration). If it looks globally true, offer to draft a GitHub issue at https://github.com/Thousand-Cuts/wf-toolkit/issues with the endpoint, API version, date, and observed-vs-documented behavior. Never edit the installed plugin's files.

## Cross-references

- `workfront-calc-fields` — calc body authoring
- `workfront-api` — auth, pagination, External Lookups, parameterValues reads
