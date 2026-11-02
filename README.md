# SONIC / RADAR — the one-page version

This is the **simple private gig list** for Maastricht. It launches straight into **all upcoming announced events**, in chronological order. No dashboards, onboarding, accounts or configuration.

## Option 1: Just use it on your computer (the simplest)

- Download `SONIC-RADAR.html` (supplied separately from this ZIP).
- Double-click it, or drag the file into Chrome, Firefox, Edge or Safari.
- Bookmark it (Ctrl+D on Windows/Linux, Command+D on Mac).
- It has the complete existing event list, even without an internet connection. All events open their original venue/promoter pages for tickets and details.

**Limitation:** A standalone file is a saved snapshot. Opening it again next week will remove expired dates automatically, but it **will not discover newly announced events** by itself. For that, use Option 2.

## Option 2: Have a bookmarkable web address that refreshes automatically

A one-time deployment with GitHub Pages. The workflow checks supported official venue sites approximately every **12 hours** (best effort) and updates the published event feed. It is automatic *only after you publish this project*.

1. Make a free account at https://github.com/ and create a **public repository** named `sonic-radar`. Keep the default branch `main`.
2. **Extract this ZIP** and upload the **contents** of the `sonic-radar-personal` folder to the top level of your repository, including `.github`, `data` and `scripts`. On GitHub select **Add file → Upload files** and commit the upload. The homepage file must appear in the repository as `/index.html`, not inside another folder.
3. In your repository choose **Settings → Pages → Build and deployment → Source → GitHub Actions**. A publishing workflow is already included—do not create a separate template.
4. Under **Actions**, open **Refresh SONIC RADAR and publish** and click **Run workflow**. After it finishes, go to **Settings → Pages** and click **Visit site**.
5. Bookmark the URL, usually `https://YOUR_USERNAME.github.io/sonic-radar/`. From then on, opening it shows the events immediately. The page fetches the newest published JSON when online and uses its saved starter feed otherwise.

**Privacy:** GitHub Pages is **publicly reachable** with the free GitHub plan. If you want the site itself to stay entirely private, use Option 1; it needs no online publication. Even a private GitHub repository is not a private website on most GitHub Pages plans.

**How fresh and comprehensive is it?** The starter selection of 42 announced dates was checked on **2 November 2026**. The automatic scanner covers Muziekgieterij, Complex, Nieuwe Nor and Effenaar, plus optional Ticketmaster Discovery API results if you add `TICKETMASTER_API_KEY` under your GitHub repository's Actions secrets. Belgian and German venues and promoters in the initial dataset are *not all automatically scanned*. The crawler can miss shows, and tickets/prices are not live. Click each entry to confirm.

If the workflow fails, the previous list remains visible instead of going blank. Check the **Actions** log for why. For the most complete new dates across BE/DE, a broader source set would need to be added to the scanner.

## Files in the project

- `index.html`: the complete, minimal frontend with a bundled backup of the original 42 listings
- `data/events.json`: the refreshed feed read by the hosted site
- `data/events.js`: companion output used by the scanner
- `scripts/refresh_events.py`: best-effort source scanner
- `scripts/test_refresh_events.py`: parser tests
- `requirements.txt`: Python dependencies
- `.github/workflows/refresh-events.yml`: automated scanner and GitHub Pages publishing

No databases, backend, passwords or paid services are necessary.
