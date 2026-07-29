# Setup — Workfront Calculated Fields Project (Claude.ai)

5-minute setup for using the Workfront Calculated Fields assistant via Claude.ai chat.

## Prerequisites

- Any Claude.ai plan (Free, Pro, Max, Team, or Enterprise — Projects are available on all plans)
- The repo files on your local machine. Three ways to get them:
  - **No terminal:** open this repo on github.com → green **Code** button → **Download ZIP** → unzip wherever you like.
  - **`gh` CLI:** `gh repo clone <owner>/<repo>` (this repo's GitHub path)
  - **`git`:** `git clone <this-repo-clone-url>`

  All steps below assume you've opened the unzipped/cloned folder.

## Steps

1. **Create a new Project in Claude.ai.**
   Go to [claude.ai/projects](https://claude.ai/projects) and click **+ New Project**. Name it "Workfront Calculated Fields."

2. **Add the custom instructions.**
   Open the project, click into the instructions field, and paste the entire contents of `claude-projects/calculated-fields/project-instructions.md` (from this repo).

3. **Upload the knowledge files.**
   In the project's Knowledge panel (right side of the project screen), upload every file in `knowledge/calculated-fields/`. Claude will reference these in every chat within the project.

4. **(Optional) Upload examples.**
   For ready-made starter patterns, upload everything under `examples/calculated-fields/` as well. Claude will pull from these when you ask for snippets.

5. **Start a chat.** Try one of:
   - "I need a calculated field on a Task form that shows how many days overdue the task is."
   - "My calculated field is returning blank. Here's the expression: [paste expression]"
   - "How do I reference a custom field on the parent project from a task-level calc field?"
   - "What format should I use for a budget variance field — Number or Currency?"

## Updates

When this repo updates a knowledge file, re-download the file from GitHub (or `git pull` if you cloned) and re-upload it to your Project's Knowledge panel. There's no automatic sync — Claude.ai Projects are per-user setups.

To check what changed in this repo, watch the repo's commit history on GitHub.

## Why this works

Workfront calculated fields have non-obvious rules that trip up even experienced admins: the format-is-permanent constraint, the `$$TODAY` staleness problem, the child→parent-only traversal direction, the `NOT()`/`NOTBLANK()` prohibition, and the multi-form formula-identity requirement. The knowledge files capture these patterns so Claude applies them immediately instead of guessing.

## Troubleshooting

- **Claude shows a valueexpression instead of a calculated field expression:** the instructions scope this project to calc fields only, but remind it in chat: "I'm building a calculated custom field, not a text-mode report column."
- **Claude doesn't always put the Format line before the expression:** this is in the instructions but prompting helps — ask "please state the Format before every expression."
- **Claude suggests NOT() or NOTBLANK():** these are invalid in calc fields. Correct it with "use !() and !ISBLANK() — NOT() and NOTBLANK() are not valid here." The rules are in the knowledge base but reminding helps.
- **Claude invents field names:** remind it to ask you for the exact label and not to guess custom field names.
