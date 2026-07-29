# Setup — Workfront Text Mode Project (Claude.ai)

5-minute setup for using the Workfront text-mode assistant via Claude.ai chat.

## Prerequisites

- Any Claude.ai plan (Free, Pro, Max, Team, or Enterprise — Projects are available on all plans)
- The repo files on your local machine. Three ways to get them:
  - **No terminal:** open this repo on github.com → green **Code** button → **Download ZIP** → unzip wherever you like.
  - **`gh` CLI:** `gh repo clone <owner>/<repo>` (this repo's GitHub path)
  - **`git`:** `git clone <this-repo-clone-url>`

  All steps below assume you've opened the unzipped/cloned folder.

## Steps

1. **Create a new Project in Claude.ai.**
   Go to [claude.ai/projects](https://claude.ai/projects) and click **+ New Project**. Name it "Workfront Text Mode."

2. **Add the custom instructions.**
   Open the project, click into the instructions field, and paste the entire contents of `claude-projects/textmode/project-instructions.md` (from this repo).

3. **Upload the knowledge files.**
   In the project's Knowledge panel (right side of the project screen), upload every file in `knowledge/textmode/`. Claude will reference these in every chat within the project.

4. **(Optional) Upload examples.**
   For ready-made starter patterns, upload everything under `examples/textmode/` as well. Claude will pull from these when you ask for snippets.

5. **Start a chat.** Try one of:
   - "I need a view that shows project name, owner, planned completion date, and a calculated days-remaining column."
   - "My filter is hitting a 'too many hops' error. Here's what I have: [paste filter]"
   - "How do I build a combined column with bold labels and line breaks?"

## Updates

When this repo updates a knowledge file, re-download the file from GitHub (or `git pull` if you cloned) and re-upload it to your Project's Knowledge panel. There's no automatic sync — Claude.ai Projects are per-user setups.

To check what changed in this repo, watch the repo's commit history on GitHub.

## Why this works

Workfront text mode has quirks that aren't well-documented in one place — `valuefield` vs `valueexpression` distinctions, the 2-level filter limit and how `EXISTS` bypasses it, why conditional formatting silently fails on `valueexpression` columns, the shared-column pattern for bold labels. The knowledge files capture these patterns so Claude applies them immediately instead of guessing.

## Troubleshooting

- **Claude doesn't seem to know about a specific quirk:** verify the relevant knowledge file is uploaded. Check the project's Knowledge panel against `knowledge/textmode/` — every file there should be listed.
- **Claude is inventing field names:** remind it in chat to consult the API Explorer at `experienceleague.adobe.com` and not to guess. This behavior is in the instructions but reminding helps.
- **Claude is suggesting Fusion or API workarounds:** the instructions tell it to stay within Workfront, but ask "stick to text mode only" if it drifts.
