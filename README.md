# Job Hunt

Your daily job search, done for you by Claude.

## What it does

- Searches LinkedIn every day for the kind of job you want, plus the careers sites of the companies you choose to watch. That includes Google, Microsoft, IBM, Naver and SAP, read from their public job feeds. SAP offers come as links only, because the site blocks automated reading.
- Matches each offer to your profile and keeps the best ones in a short list.
- Writes a tailored one-page CV and cover letter for each top offer (both as PDF and Word DOCX). The PDF CV uses a clean single-column design (accent colour picked for the sector, optional photo, bold key results) that applicant tracking systems (ATS) still read reliably; the DOCX keeps a plain layout for portals like Workday. The cover letter is edited to remove stock AI phrasing, without adding anything that isn't in your profile.

## Install

1. Open **Claude Code**: the **Code** tab of the Claude desktop app, or the `claude` command line. Mac, Windows 11 and Linux all work.
   > The **Chat** tab and claude.ai can't install plugins or run the plugin's scripts. If Claude there offers to "save a job-hunt skill" instead, decline: you'd get a simplified copy without the LinkedIn script, the careers-site feeds or the ATS checks.
2. Install **Google Chrome** and **Python 3.10 or newer**. On Windows, in a terminal: `winget install Python.Python.3.12` and `winget install Google.Chrome`. On a Mac: `brew install python` if needed. Setup checks both for you.
3. Run these two commands in Claude Code, one after the other:

```
/plugin marketplace add gabcal07/job-hunt-plugin
/plugin install job-hunt@job-hunt-marketplace
```

4. Nothing else to install: web pages are read with Claude's built-in WebFetch (and the app's browser when a page needs it), so it works on the Pro plan.

## Start

Run `/job-hunt:setup`. It asks you a few questions. Have your CV ready, and your LinkedIn profile saved as a PDF (on your profile: More → Save to PDF).

## Every day

Open `~/job-hunt/runs/<date>/shortlist.md` to see today's offers. Each offer has its own folder containing only what you need:

- `cv.pdf` and `cv.docx`: the tailored CV.
- `cover-letter.pdf` and `cover-letter.docx`: the tailored letter.
- `notes.md`: why the offer was picked, the gaps to know about, and which CV file to upload.

Everything else (the posting, the edited profile, the intermediate pages) is in the folder's `_work` subfolder, and you can ignore it. You apply yourself, on LinkedIn or the company site.

## Change what you're looking for

Either edit `~/job-hunt/JOB_SEARCH.md` in any text editor, or tell Claude what to change, for example:

```
/job-hunt:settings add Lyon
```

Example lines in `JOB_SEARCH.md` (add as many as you like):

- `Cities: Paris, Lyon, also remote in France`
- `Contract: CDI, alternance`
- under `## Job titles to search`: one title per line
- under `## Companies to watch`: companies whose careers sites are checked every day, e.g. `- Doctolib — https://careers.doctolib.com` (the link is optional)

## Credits

Bundled, unmodified, under its MIT licence: [humanizer](https://github.com/blader/humanizer) (Siqi Chen). See `skills/humanizer/SOURCE.md`.

## Commands

| Command | What it does |
|---|---|
| `/job-hunt:setup` | Guided interview to start (profile and settings) |
| `/job-hunt:run` | Run the search now |
| `/job-hunt:settings` | Show or change what you are looking for |
| `/job-hunt:tailor <LinkedIn job URL>` | Write a CV and cover letter for one offer |
| `/job-hunt:profile` | Build your profile, or update it with a change |
| `/job-hunt:canva` | Optional: a polished Canva version of your CV |

## Optional: Apify (free) for more reliable LinkedIn results

LinkedIn limits how many offers one internet connection can read per day, and it limits a VPN or office network even more. With a free [Apify](https://apify.com) account, the daily search reads LinkedIn through Apify's servers instead:

- It finds every offer from the **last week** that you haven't already seen, so a day the app was closed is still covered.
- Every offer comes with its full description, instead of only the 20 best-ranked ones.
- Nothing is read from your own connection, so LinkedIn's limits and VPN blocks don't apply.
- **Welcome to the Jungle** is added for cities in France.

A typical run takes 3 to 5 minutes. In one test it found 32 new offers.

1. Create a free account at apify.com. No credit card is needed.
2. Copy your API token from **Settings → API & Integrations**.
3. In Claude, paste it into this plugin's settings (**Customize → Plugins → job-hunt**, or `/config`). Start a new session.

**Cost:**
- The free plan gives $5 of credit a month.
- One offer costs $0.0004. Offers you've already seen are skipped before they're fetched, so you never pay twice for the same one. A typical day costs 1 to 4 cents, about $1–2 a month.
- The plugin stops using Apify at $4.50 a month and goes back to reading LinkedIn directly, so you're never charged.
- To change how many offers each search fetches, set `Apify offers per search` in `JOB_SEARCH.md`.

The token is kept in Claude's secure storage. A small start-up step copies it into the plugin's private folder so the search scripts can read it. If that step can't run (on Windows without `python3` on the PATH), set an `APIFY_TOKEN` environment variable instead.

Apify also publishes its own Claude Code plugin (`/plugin marketplace add apify/apify-claude-code-plugin`) for scraping other sites by chat. The daily search doesn't need it.

## Optional: a Canva version of your CV

The daily CVs are always plain PDFs, so they work for everyone. If you use Canva and want a hand-polished master CV there:

1. Install Canva's plugin: `/plugin install canva@claude-plugins-official`, then sign in to Canva when asked.
2. Run `/job-hunt:canva`. Claude builds the design from your profile, shows it to you, and saves a PDF plus a link to edit it in Canva.

Any Canva account works for a new design. Filling your own Canva template needs a paid Canva plan. Edits you make by hand in Canva stay in Canva; run `/job-hunt:canva update` after you change your profile.

## Privacy

- You're responsible for disclosing AI assistance where an employer requires it. Editing the wording doesn't make the content human-written.

- Everything stays on your computer, in `~/job-hunt/`.
- The plugin only reads LinkedIn. It never applies to a job or sends a message for you.

## Limits

- LinkedIn only, for now.
- The daily run needs the Claude app open at the scheduled time.
- LinkedIn may slow down its responses, so a run can take longer than usual.
