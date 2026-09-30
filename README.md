# Frontline Media: Instagram autopost

Publishes `queue.json` to @frontlinemedia.eu on schedule. GitHub Actions runs `publish.py` every 5 minutes,
and it posts anything whose `publish_at` time has passed (never more than 3 hours late).
Media is served from GitHub Pages; the access token lives in the repo secret `IG_ACCESS_TOKEN`.

- **Pause everything:** add an empty file called `PAUSED` to the repo. Delete it to resume.
- **What was posted:** `state.json` (media IDs, times, errors).
- **Add content:** put files in `media/`, add entries to `queue.json` (`REELS`, `CAROUSEL`, `IMAGE` or `STORY`).
- **Test without posting:** `IG_ACCESS_TOKEN=… python3 publish.py --check`

GitHub's scheduler can run a few minutes late at busy times, so posts can land up to ~15 minutes after their slot.
