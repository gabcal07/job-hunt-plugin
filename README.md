# Job Hunt

Your daily job search, done for you by Claude.

## What it does

- Searches LinkedIn every day for the kind of job you want, plus the careers sites of the companies you choose to watch.
- Matches each offer to your profile and keeps the best ones in a short list.
- Writes a tailored one-page CV and cover letter for each top offer (the CV as PDF and Word DOCX, the letter as PDF). The PDF CV uses a clean single-column design (accent colour picked for the sector, optional photo, bold key results) that applicant tracking systems (ATS) still read reliably; the DOCX keeps a plain layout for portals like Workday. The cover letter is edited to remove stock AI phrasing, without adding anything that isn't in your profile.

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

Open `~/job-hunt/runs/<date>/shortlist.md` to see today's offers. Each offer has its own folder with a tailored CV and cover letter (PDF). You apply yourself, on LinkedIn or the company site.

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
