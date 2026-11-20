---
name: job-hunt
description: Personal job-search assistant. Reads the user's plain-language JOB_SEARCH.md (contracts, cities, job titles, target companies, offers per day…), searches LinkedIn job postings, scores and shortlists them against the user's profile, and writes a tailored one-page CV and cover letter PDF for the best offers. Also builds the profile from a CV, LinkedIn and notes, and runs a guided setup. Use for "find me jobs", "job hunt", setting up or changing a job search, building or updating a job profile, tailoring a CV or cover letter to an offer, or when the scheduled job-hunt run fires.
---

# job-hunt

**Paths.**
- `S` is this skill's folder: `${CLAUDE_PLUGIN_ROOT}/skills/job-hunt`, or the folder this SKILL.md is in.
- `D` is the user's data folder: `$JOB_HUNT_HOME`, else `~/job-hunt`.
- Scripts are stdlib Python and run as `python3 $S/scripts/<x>.py`. There is nothing to install except Google Chrome, which turns HTML into PDF.

```
D/JOB_SEARCH.md            THE file the user edits (plain language). Read on every run.
D/profile/profile.json     CV facts, the single source of truth (shape: S/references/profile-schema.json)
D/profile/profile.md       stories, motivations and the "To confirm" list (used for letters)
D/profile/sources/         raw extracts: cv.md, linkedin.md, notes.md, the original CV, photo.jpg
D/state/settings.json      the agent's reading of JOB_SEARCH.md (regenerated every run)
D/state/seen.json          job ids already evaluated
D/runs/YYYY-MM-DD/         jobs.json, scores.json, shortlist.md, and one folder per selected offer
```

**Talking to the user.** Assume they are not technical. Use plain words, never ask them to run commands, and show file paths as clickable links. Never apply to jobs, message anyone or log in for them.

**Models.** You (the main agent) decide: the interpretation of the settings, the merges, the selection and every review. Workers do the groundwork in parallel: Sonnet for extraction, scoring and tailoring, Haiku for transcription. Workers write only into their own folder and never commit.

## Mode: setup (guided, first time)
1. Run `python3 --version`, and check that Chrome is available with `python3 $S/scripts/render.py --check-chrome`. Explain any problem simply, with the install link.
2. `mkdir -p D/{profile/sources,state,runs}`. If `D/JOB_SEARCH.md` already exists, offer to keep it, or show it and change it.
3. Interview the user with AskUserQuestion, at most 4 questions per call, multiSelect where it fits:
   - contract types
   - cities
   - level
   - remote
   - job titles (free text through "Other")
   - target companies (optional)
   - offers per day
   - CV language

   Ask for the start date and dealbreakers in plain chat. Fill `S/assets/JOB_SEARCH.template.md` with the answers, write it to `D/JOB_SEARCH.md`, and show it. Tell them: "You can edit this file anytime, or just tell me what to change."
4. Ask for their CV (a file path, or drag it in), their LinkedIn profile URL, and optionally a notes or portfolio folder. Copy them into `D/profile/sources/`. Then run **build-profile**.
5. Run **settings** once so they see how their file is understood.
6. Offer a daily run:
   - Create it with `create_scheduled_task` (desktop) at around 8am, with the prompt "/job-hunt:run". Without the desktop app, use `CronCreate`, or explain how to run `claude -p "/job-hunt:run"` from cron.
   - Tell them to open the task in the app and click **Run now** once to approve its tools.
   - Tell them it only runs while the app is open.

## Mode: build-profile (or update-profile)
Spawn these in parallel. Each writes only its own file in `sources/`:
- **cv.md**: Haiku transcribes the CV verbatim and adds layout notes.
- **linkedin.md**: Sonnet uses the Chrome DevTools MCP.
  - If an authwall or login page shows, stop and ask the user to log in in that Chrome window.
  - Read the main profile, then `/details/{experience,education,skills,certifications,projects,languages,recommendations}/`.
  - Read only. Never click Connect, Message or Edit.
- **notes.md** (only if notes were given): Sonnet extracts recent roles and achievements:
  - CV bullets in EN and FR, each with a source and a confidentiality tag
  - skills actually used
  - STAR stories
  - open questions

  It never invents and marks anything uncertain `[unconfirmed]`.

Then you merge everything into `profile.json`, following `S/references/profile-schema.json`, with a stable `id` and `tags` on every entry, and into `profile.md` (positioning, stories, motivations).
- Every conflict between sources and every unconfirmed fact goes into `## To confirm` at the top of `profile.md`. Ask the user about the important ones.
- Render the master CV to check it: `render.py cv --profile D/profile/profile.json --lang en --out D/profile/master-en.pdf`. It may be 2 pages, since it holds everything.

**Updates:** when the user says something like "I now do X" or "add my certification", edit `profile.json` and `profile.md` directly, keep every fact traceable, and re-render the master.

## Mode: settings
1. Read `D/JOB_SEARCH.md` and interpret it into `D/state/settings.json`, following `S/references/settings-schema.md` exactly.
2. `python3 $S/scripts/settings.py --check D/state/settings.json`. If it fails, fix your interpretation. If the problem is in the user's file, explain it in plain words.
3. Show the user a short summary: the number of searches, cities, titles, target companies, offers per day, and your `notes` (the interpretations you made).
4. If they ask for a change ("add Lyon", "5 more offers"), edit `JOB_SEARCH.md` in their own style, then repeat from step 1.

## Mode: run (the scheduled job; arguments may override for this run only)
1. **Settings:** do the settings steps 1–2. If the file has no titles or no cities, stop and report.
2. **Search:** `python3 $S/scripts/linkedin_search.py --settings D/state/settings.json --seen D/state/seen.json --out D/runs/<today>/jobs.json`
   - If the output says `"blocked": true`, continue with what was collected and say so. Never retry in a loop.
   - For jobs with an empty `description`, open the URL with the Chrome DevTools MCP. If that fails too, drop the job.
3. **Score:** batches of about 15 jobs, one Sonnet worker per batch, in parallel. Give each worker `S/references/scoring.md`, `profile.json`, `settings.json` (including `preferences`, `target_companies` and `bonus_companies`) and its batch. Merge the results into `scores.json`.
4. **Select (you):**
   - Re-read the top postings and fix any wrong scores.
   - Pick at most `top_n` jobs with `score ≥ min_score`.
   - Write `shortlist.md`: a table of every scored job (score, title, company, city, link, why), with ⭐ on the selected ones, followed by a "How I read your settings" line (the `notes`).
5. **Tailor:** one Sonnet worker per selected job, in parallel, each in `runs/<today>/<company>-<role>/`. Each worker follows `S/references/cv-writing.md`:
   - write `tailored.json`, `letter.json` and `notes.md`
   - `render.py cv --profile tailored.json --lang L --out cv.pdf [--photo D/profile/sources/photo.jpg]`
   - `render.py letter --profile tailored.json --letter letter.json --lang L --out cover-letter.pdf`

   `L` is the posting's language when `cv_language` is "match"; anything other than fr/en becomes en. Exit code 3 means the CV is over one page: trim it and re-render.
6. **Review (you, every job):**
   - Every fact, skill, number and date in `tailored.json` and the letter must trace back to `profile.json` or `profile.md`.
   - The CV must be 1 page, and the letter must be specific to the company.
   - On a failure, send it back to the worker once with the exact problems. If it fails again, fix it yourself or drop it.
   - Mark the reviewed rows ✅.
7. If `D` is a git repo, commit the run (`run <today>`). Never push.
8. **Report** in plain words: how many offers were found, scored and selected; a link to `shortlist.md`; a link to each folder; and anything blocked or misread.

## Mode: tailor-one (an offer the user found)
Fetch the posting with `linkedin_search.py`'s detail parser: `python3 $S/scripts/linkedin_search.py --job-url URL --out ...`. If it isn't a LinkedIn URL, read the page with the browser or WebFetch. Score it, then run tailor steps 5–6 for that one job in `runs/<today>/`.

## Safety
- Read-only on LinkedIn: no applying, messaging or connecting. Requests are polite and stop when blocked.
- Personal data stays in `D`. Never write it into this skill folder.
