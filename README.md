# Job Hunt

**A daily job search that runs in Claude Code.** It searches LinkedIn, the careers sites of the companies you watch, and Welcome to the Jungle. Then it ranks the offers against your profile and writes a tailored CV and cover letter for the best ones. You review them and apply.

```
/job-hunt:setup   once: your profile and what you're looking for
/job-hunt:run     every day (or on a schedule): offers ranked, CVs and letters ready
```

→ [Install and setup](INSTALL.md)

## What you get every morning

- **A ranked shortlist** of new offers, scored 0–100 against your skills, level, contract, cities and the wishes you wrote in plain words.
- For each top offer, **a CV and cover letter written for that offer**, as PDF and Word, each on one page.
- **A review sheet** for each offer: the must-haves you meet, the ones you don't (marked GAP), and which file to upload.

The plugin never applies for you, never logs in, and never invents anything: every fact in a CV or letter comes from your profile, and code checks every number and date before you see them.

## Where it looks

| Source | How | Notes |
|---|---|---|
| **LinkedIn** | Public job listings, no login. With a free [Apify](INSTALL.md#optional-apify-free-for-linkedin-and-welcome-to-the-jungle) account, through Apify's servers | With Apify: every offer from the last week, with full descriptions, and no limits on your connection |
| **Companies you watch** | Their job platform's public feed (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee) or their own (Google, Amazon, Microsoft, IBM, Naver) | SAP blocks automated reading, so its offers come as links to open yourself |
| **Welcome to the Jungle** | Through Apify, for cities in France | Many startups and scale-ups that don't post on LinkedIn |

Offers already shown are remembered, so you never see the same one twice, even if it appears on two sites.

## How it works

1. **Search:** scripts fetch the offers. Your settings come from `JOB_SEARCH.md`, a plain-language file you edit.
2. **Filter:** code removes duplicates, offers you excluded, and certain mismatches, such as 4+ years required for a junior or an unwanted internship.
3. **Score:** Claude reads each remaining offer and scores the fit using a fixed rubric.
4. **Write:** for each top offer, Claude rewrites your CV and writes the letter. It uses the offer's keywords where they're true for you, and removes stock AI phrasing.
5. **Check:** code checks that the CV fits one page, that applicant tracking systems (ATS) can read it, and that no number or date in the CV or letter is missing from your profile. Then Claude reviews each letter.

Everything that is the same every day is done by code. Claude only does the judgement: scoring, writing and reviewing. That keeps a daily run fast and cheap on a Pro plan.

## What a run leaves you

```
~/job-hunt/runs/2026-11-23/
├── shortlist.md                       ← start here
├── reply-junior-ai-engineer/
│   ├── cv.pdf   cv.docx
│   ├── cover-letter.pdf   cover-letter.docx
│   ├── notes.md                       ← read before applying
│   └── _work/                         ← ignore
├── galadrim-ai-engineer/
│   └── …same files
└── *.json                             ← raw data, ignore
```

**`shortlist.md`:** the day's best 15 offers, highest score first.
- ⭐ marks the offers that got a CV and letter. ✅ means Claude reviewed them.
- Each row has the score, a link to the offer, the company, the city and the source (`linkedin`, `wttj`, `careers`).
- **Why** gives one line on the fit and what's missing. **Upload** names the CV file to send.
- Offers from sites that block automated reading are listed below the table, to open yourself.

**In each offer folder:**

| File | Use it to |
|---|---|
| `cv.pdf` | Send by email, or upload on simple job sites. It uses a clean one-column design and stays readable by applicant tracking systems. |
| `cv.docx` | Upload on application portals (Workday, Taleo, LinkedIn Easy Apply…), which read Word more reliably. |
| `cover-letter.pdf` | Send with the CV. |
| `cover-letter.docx` | Change a sentence yourself, or answer a form that asks for Word. |
| `notes.md` | Check the fit before applying: why the offer was picked, each must-have with your matching experience or a **GAP**, what was reworded, and which file to upload. |

`_work/` holds what the files are built from: the offer as read, your profile edited for this offer, and the letter's text. You never need to open it.

**To apply:** pick a ⭐ offer and read its `notes.md`, then check the two PDFs. To change something, ask Claude ("in the Reply letter, mention my hackathon first") or edit the Word files. Then open the offer's link and upload the file the **Upload** column names.

## Commands

| Command | What it does |
|---|---|
| `/job-hunt:setup` | Guided start: your profile from your CV and LinkedIn, and your search |
| `/job-hunt:run` | Run the search now |
| `/job-hunt:tailor <link>` | A CV and letter for one offer you found yourself |
| `/job-hunt:settings` | Show or change what you're looking for |
| `/job-hunt:profile` | Update your profile ("I now do X") |
| `/job-hunt:canva` | Optional: a polished Canva version of your CV |

## Privacy and limits

- Everything stays on your computer, in `~/job-hunt/`. Your Apify token, if you add one, is kept in Claude's secure storage.
- You're responsible for disclosing AI assistance where an employer requires it.
- The daily run happens only while the Claude app is open.
- A few company sites can't be read automatically (SAP). Their offers come as links.
- Without Apify, LinkedIn limits how much one connection can read, so a run can be slow and give fewer descriptions.

## Credits

Bundled, unmodified, under its MIT licence: [humanizer](https://github.com/blader/humanizer) (Siqi Chen). See `skills/humanizer/SOURCE.md`.
