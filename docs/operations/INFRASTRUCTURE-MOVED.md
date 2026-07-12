# infrastructure/ has moved

As of 2026-07-12, everything that used to live at `infrastructure/`
in this repo (`n8n-mcp/`, `n8n-workflows/`, `server-hardening/`) has
been split out into its own dedicated repository:

**`empireenglishcommunity-glitch/empire-server-forge`**

It was combined there with `empire-chronicle`'s `server-cmdbot/`
(the admin Telegram bot), since server/infrastructure operations is a
genuinely distinct concern from this repo's actual job (product code:
bots, apps, workers) — it had only been living here as a subfolder by
circumstance.

## What happened to the history

Nothing was lost. `git filter-repo --subdirectory-filter infrastructure`
extracted the exact commit history for this folder (13 original
commits) into the new repo, then merged with the separately-extracted
`server-cmdbot` history via `git merge --allow-unrelated-histories` —
every original commit from both sources is preserved and browsable in
`empire-server-forge`'s log.

If you need `infrastructure/`'s old history from within *this* repo,
it's still there — this removal is a new commit, not a rewrite of past
history.
