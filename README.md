# Job Hunt

Your daily job search, done for you by Claude.

## What it does

- Searches LinkedIn job postings every day for the kind of job you want.
- Matches each offer to your profile and keeps the best ones in a short list.
- Writes a tailored one-page CV and cover letter (PDF) for each top offer.

## Install

1. Open Claude Code (the desktop app or the command-line version) and make sure Google Chrome is installed.
2. Run these two commands, one after the other:

```
/plugin marketplace add gabcal07/job-hunt-plugin
/plugin install job-hunt@job-hunt-marketplace
```

## Start

Run `/job-hunt:setup`. It asks you a few questions. Have your CV and your LinkedIn URL ready.

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
- under `## Target companies`: companies to search on purpose

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

- Everything stays on your computer, in `~/job-hunt/`.
- The plugin only reads LinkedIn. It never applies to a job or sends a message for you.

## Limits

- LinkedIn only, for now.
- The daily run needs the Claude app open at the scheduled time.
- LinkedIn may slow down its responses, so a run can take longer than usual.
