# Setup — Workfront API Project (Claude.ai)

5-minute setup for using the Workfront API assistant via Claude.ai chat.

## Prerequisites

- Any Claude.ai plan (Free, Pro, Max, Team, or Enterprise — Projects are available on all plans)
- The repo files on your local machine. Three ways to get them:
  - **No terminal:** open this repo on github.com → green **Code** button → **Download ZIP** → unzip wherever you like.
  - **`gh` CLI:** `gh repo clone <owner>/<repo>` (this repo's GitHub path)
  - **`git`:** `git clone <this-repo-clone-url>`

  All steps below assume you've opened the unzipped/cloned folder.

## Steps

1. **Create a new Project in Claude.ai.**
   Go to [claude.ai/projects](https://claude.ai/projects) and click **+ New Project**. Name it "Workfront API."

2. **Add the custom instructions.**
   Open the project, click into the instructions field, and paste the entire contents of `claude-projects/api/project-instructions.md` (from this repo).

3. **Upload the knowledge files.**
   In the project's Knowledge panel (right side of the project screen), upload every file in `knowledge/api/`. Claude will reference these in every chat within the project.

4. **(Optional) Upload examples.**
   For ready-made starter patterns, upload everything under `examples/api/` as well. Claude will pull from these when you ask for snippets.

5. **Start a chat.** Try one of:
   - "Show me how to GET all active projects I own, including the custom field DE:Region."
   - "I'm getting a 401 on my API call — here's what I have: [paste request]"
   - "How do I set up an External Lookup field that pulls project names from the same Workfront instance?"
   - "Walk me through OAuth2 client credentials for a nightly sync script."

## Updates

When this repo updates a knowledge file, re-download the file from GitHub (or `git pull` if you cloned) and re-upload it to your Project's Knowledge panel. There's no automatic sync — Claude.ai Projects are per-user setups.

To check what changed, watch the repo's commit history on GitHub.

## Why this works

Workfront's REST API has quirks that aren't well-consolidated in one place — the version-pinning requirement, the prohibition on URL-encoding `DE:` field names, the exact JSONPath syntax for `parameterValues` in External Lookup fields, the Fusion cascade limitation workaround. The knowledge files capture these patterns so Claude applies them immediately instead of guessing from general API knowledge.

## Troubleshooting

- **Claude is using the wrong API version:** remind it in chat that `v17.0` is the default. Verify the relevant knowledge file (`01-api-fundamentals.md`) is uploaded.
- **Claude is URL-encoding `DE:` field names:** remind it that `DE:Field Name` must appear un-encoded. The rule is in `04-fields-and-naming.md` — verify that file is uploaded.
- **Claude is suggesting Fusion or text-mode workarounds:** the instructions tell it to stay within the API scope. Ask "API only please" to redirect it.
- **Claude doesn't know about External Lookup cascading behavior:** verify `12-external-lookup-fields.md` is uploaded — the cascade limitation and Fusion workaround are documented there.
