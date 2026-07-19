# Restoring this repository after the privacy purge

The published GPS data once included the unpaid drive to each pickup, whose first
leg of the day began at a habitual origin. That was fixed in the data and then
purged from git history, but a force-push does not remove the old objects from
GitHub — they stay fetchable by commit SHA until the repository itself is gone.
Deleting and recreating the repository is what actually removes them.

This file is the runbook for that. Delete it once the repo is back up.

## Before you start

A verified backup of the clean history lives outside this working copy:

```
C:\Users\Caldera\Projects\rideshare-metrics-showcase-CLEAN-BACKUP.bundle
```

It restores to commit `2d1e33d`, 41 commits, with no leaked data. Verified by
cloning it to a scratch directory and re-running the geometric scan. If anything
below goes wrong, `git clone <that bundle> <newdir>` gets everything back.

## 1. Delete the repository

GitHub only allows this from the web UI, and it needs a scope the git credential
does not carry, so it has to be done by hand:

<https://github.com/shehzadqayum/rideshare-metrics-showcase/settings> → bottom of
the page → **Delete this repository** → type the name to confirm.

Safe to do: the repo had 0 forks, 0 stars, 0 watchers and a network count of 0,
so nothing survives elsewhere to keep the old objects alive.

## 2. Recreate it, empty

<https://github.com/new>

- Name: `rideshare-metrics-showcase`
- Visibility: **Public**
- Description:
  `Demonstration site for ride-share analytics tools built during 890+ London Uber trips — routes, metrics, demand and cost data, all real.`
- Do **not** add a README, .gitignore or licence — the push supplies everything.

## 3. Push the clean history

From this working copy:

```bash
git push -u origin main
```

The remote URL is unchanged, so nothing needs reconfiguring.

## 4. Re-enable Pages

Settings → Pages → Source: *Deploy from a branch* → `main` / `/docs` → Save.
The site returns to <https://shehzadqayum.github.io/rideshare-metrics-showcase/>
after a minute or two.

## 5. Confirm the purge

Old SHAs must now 404 rather than serve data:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://raw.githubusercontent.com/shehzadqayum/rideshare-metrics-showcase/c150dbf2fd82ac7550c50dec9ddf2256b42c8b2f/docs/data/weeks.json
```

`404` means the old objects are gone. `200` means they are still being served —
in that case the deletion did not take effect, so check step 1 completed.
