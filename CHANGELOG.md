# Changelog

## 1.1.3 — 2026-08-06

Automated knowledge sync from the maintainers' verification pipeline (scrub gate + validation passed).

## 1.1.2 — 2026-08-06

Automated knowledge sync from the maintainers' verification pipeline (scrub gate + validation passed).

## 1.1.1 — 2026-08-06

Automated knowledge sync from the maintainers' verification pipeline (scrub gate + validation passed).

## 1.1.0 — 2026-08-06

Knowledge sync from the maintainers' verification pipeline (all findings
tested against live tenants before entering the record):

- **api:** status/enum corrections (Project "Approved" is `APR` not `APV`;
  On Target stores `ON` not `OT`), convertToTask effort model, templateID
  project creation, proofing recipes, silent-no-op traps, API v20-22 diffs.
- **custom-forms:** parameter-type coverage matrix, display-logic REST
  surface (categoryCascadeRules), audit recipes, metadata census.
- **permissions:** ALVPER capability matrix survey, fieldAccessPrivileges
  enum, inheritance walker, layout-template gotcha, internal-endpoint
  findings.
- **reports:** pre-flight validation, filter/view patterns, runtime schema
  discovery, sanitizer rules.
- **textmode/calculated-fields/business-rules:** assorted verified gotchas.

All notable changes to this plugin are documented here. Versioning follows semver: patch for fixes, minor for new skills/features, major for breaking changes.

## 0.1.0 — 2026-07-29

Initial public release.

- Seven skills: `workfront-textmode`, `workfront-api`, `workfront-calc-fields`, `workfront-custom-forms`, `workfront-permissions`, `workfront-business-rules`, `workfront-reports`.
- Per-topic knowledge bases (`knowledge/`), ready-to-paste examples (`examples/`), and Claude.ai Project recipes (`claude-projects/`).
- Environment credential management via `/wf-env-add`, `/wf-env-use`, `/wf-env-list`, `/wf-env-remove` — register each environment of your Workfront instance (`prod`, `preview`, `sandbox`); API keys stay in `~/wf-envs/<slug>/.env`, never in chat.
- pytest + shell smoke tests for skill scripts.

This repo was extracted from a longer-running internal toolkit. Provenance notes in `knowledge/` may cite pre-0.1.0 internal version numbers and dates; that internal history is not part of this repo.
