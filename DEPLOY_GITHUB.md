# Deploy to GitHub Actions (free cloud, no command line)

This runs both monitors in GitHub's cloud on a schedule, so nothing has to stay
on at home. All clicks — no git, no terminal.

## 1. Make a free GitHub account
Go to https://github.com/signup. Free plan is all you need. (I can't create the
account for you — you'll do this part.)

## 2. Create the repository
- Click the **+** (top right) → **New repository**.
- Name it e.g. `big-sur-camp-watcher`.
- Set it to **Public** — this makes Actions completely free with no minute limits.
  (Your Pushover keys are NOT in the code, so nothing secret is exposed. Only the
  code and your target weekend dates are visible. Prefer Private? Fine too — you
  just get 2,000 free minutes/month, enough for the camply scans.)
- Click **Create repository**.

## 3. Upload the files
- On the new repo page, click **uploading an existing file** (or **Add file →
  Upload files**).
- Drag in everything from the `big-sur-camp-watcher` folder EXCEPT `.env`
  (your keys) — the `.gitignore` already excludes it, but don't upload it manually.
  Include the hidden `.github` folder so the workflows come along. If drag-and-drop
  skips `.github`, use **Add file → Create new file** and type
  `.github/workflows/ventana.yml` as the name, then paste the file's contents
  (same for `scan.yml`).
- Click **Commit changes**.

## 4. Add your Pushover keys as secrets
- Repo → **Settings** → **Secrets and variables** → **Actions** → **New
  repository secret**.
- Add two secrets:
  - Name `PUSHOVER_PUSH_TOKEN`, value `a1fts4axtbdc11g17udd58kqh3kksv`
  - Name `PUSHOVER_PUSH_USER`,  value `uvqhtgkwn78hqdgbgneevvog5xv83i`
- These are encrypted and never visible in logs or to the public.

## 5. Turn it on and test
- Go to the **Actions** tab. If prompted, click **I understand my workflows,
  enable them**.
- Click **ventana-monitor** → **Run workflow** to fire a manual test. Within a few
  minutes you should get a Pushover ping if site 49/50 is open on any target
  weekend (49 was open for 9/25 at last check, so this is a good live test).
- After that it runs automatically: camply every 15 min, Ventana every 30 min.

## Things to know
- **Re-alerts:** GitHub wipes the disk between runs, so the "already alerted"
  memory doesn't persist — if a site stays open, you may get pinged again each run.
  Rare for Ventana, and you'll likely book it fast anyway. Tell me if it's noisy
  and I'll add caching to dedupe.
- **Bot detection:** Hyatt is hit from GitHub's datacenter IPs here, which are more
  likely to draw a CAPTCHA than your home IP. If the Ventana job starts failing or
  returning nothing while the site clearly has openings, that's the cause — we'd
  move just the Ventana piece to a home machine (the camply scans are unaffected).
- **Editing target dates later:** edit `search_config.yaml` or the `DATE_RANGES`
  in `ventana_monitor.py` directly on GitHub (pencil icon) and commit.
