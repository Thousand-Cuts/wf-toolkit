# Changelog

All notable changes to this plugin are documented here. Versioning follows semver: patch for fixes, minor for new skills/features, major for breaking changes.

## 0.1.0 — 2026-07-29

Initial public release.

- Seven skills: `workfront-textmode`, `workfront-api`, `workfront-calc-fields`, `workfront-custom-forms`, `workfront-permissions`, `workfront-business-rules`, `workfront-reports`.
- Per-topic knowledge bases (`knowledge/`), ready-to-paste examples (`examples/`), and Claude.ai Project recipes (`claude-projects/`).
- Environment credential management via `/wf-env-add`, `/wf-env-use`, `/wf-env-list`, `/wf-env-remove` — register each environment of your Workfront instance (`prod`, `preview`, `sandbox`); API keys stay in `~/wf-envs/<slug>/.env`, never in chat.
- pytest + shell smoke tests for skill scripts.

This repo was extracted from a longer-running internal toolkit. Provenance notes in `knowledge/` may cite pre-0.1.0 internal version numbers and dates; that internal history is not part of this repo.
