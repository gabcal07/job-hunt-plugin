# Install and setup

## Requirements

- **Claude Code**: the **Code** tab of the Claude desktop app, or the `claude` command line. It runs on Mac, Windows 11 and Linux, and works on the Pro plan.
  > The **Chat** tab and claude.ai can't install plugins or run the plugin's scripts. If Claude there offers to "save a job-hunt skill" instead, decline. You'd get a simplified copy without the LinkedIn script, the careers-site feeds or the ATS checks.
- **Python 3.10 or newer**, to run the search scripts:
  - Windows: `winget install Python.Python.3.12`
  - Mac: `brew install python`
- **Google Chrome**, to turn the CVs and letters into PDFs. It runs in the background. On Windows: `winget install Google.Chrome`.

Setup checks Python and Chrome for you. Nothing else is needed: no browser extension and no MCP server. Web pages are read with Claude's built-in WebFetch, or the app's browser when a page needs it.

## Install

Run these two commands in Claude Code, one after the other:

```
/plugin marketplace add gabcal07/job-hunt-plugin
/plugin install job-hunt@job-hunt-marketplace
```

## First run

Run `/job-hunt:setup`. It asks a few questions (contracts, cities, level, job titles, companies to watch, offers per day), then builds your profile. Have these ready:

- your CV, as a file;
- your LinkedIn profile saved as a PDF (on your profile: **More → Save to PDF**);
- optionally, anything else that shows your work: old cover letters, a portfolio, a GitHub profile, notes.

At the end it offers a daily run at about 8am. The scheduled run only happens while the Claude app is open. If the app is closed at that time, it runs the next time you open it.

## Optional: Apify (free) for LinkedIn and Welcome to the Jungle

Without Apify, the plugin reads LinkedIn directly from your connection. LinkedIn limits that, especially through a VPN or office network, and gives full descriptions for only the 20 best-ranked offers.

With a free Apify account:
- LinkedIn is read through Apify's servers, so its limits don't apply.
- It covers every offer from the last week that you haven't already seen, each with its full description.
- Welcome to the Jungle is added for cities in France.

To connect it:
1. Create a free account at [apify.com](https://apify.com). No credit card is needed.
2. Copy your API token from **Settings → API & Integrations**.
3. In Claude, paste it into this plugin's settings (**Customize → Plugins → job-hunt**, or `/config`).
4. Start a new session.

**Cost:**
- The free plan gives $5 of credit a month.
- One offer costs $0.0004. Offers you've already seen are skipped before they're fetched, so a typical day costs 1 to 4 cents (about $1–2 a month).
- The plugin stops using Apify at $4.50 a month and goes back to reading LinkedIn directly, so you're never charged.
- To change how many offers each search fetches, set `Apify offers per search` in `JOB_SEARCH.md` (default 15).

The token is kept in Claude's secure storage. A small start-up step copies it into the plugin's private folder so the search scripts can read it. If that step can't run (on Windows without `python3` on the PATH), set an `APIFY_TOKEN` environment variable instead.

Apify also publishes its own Claude Code plugin (`/plugin marketplace add apify/apify-claude-code-plugin`) for scraping other sites by chat. The daily search doesn't need it.

## Optional: a Canva version of your CV

1. Install Canva's plugin: `/plugin install canva@claude-plugins-official`, and sign in to Canva when asked.
2. Run `/job-hunt:canva`. Claude builds a design from your profile, shows it to you, and saves a PDF plus a link to edit it in Canva.

Any Canva account works for a new design. Filling your own Canva template needs a paid Canva plan. Edits you make by hand in Canva stay in Canva; run `/job-hunt:canva update` after you change your profile.

## Update

```bash
claude plugin marketplace update job-hunt-marketplace
```

```bash
claude plugin update job-hunt@job-hunt-marketplace
```

Then start a new session.

## Change what you're looking for

Edit `~/job-hunt/JOB_SEARCH.md` in any text editor, or tell Claude what to change, for example `/job-hunt:settings add Lyon`.

Example lines:

- `Cities: Paris, Lyon, also remote in France`
- `Contract: CDI, alternance`
- under `## Job titles to search`: one title per line
- under `## Companies to watch`: companies whose careers sites are checked every day, e.g. `- Doctolib — https://careers.doctolib.com` (the link is optional)
- under `## Never show me`: words and companies to exclude
- under `## What I want / avoid`: anything else, in your own words. The scoring reads it.

## Troubleshooting

- **LinkedIn is slow, or the report mentions many 429s:** LinkedIn is limiting your connection. Turn off your VPN, or connect Apify.
- **"LinkedIn banned the IP" (999):** wait a few hours, ideally off VPN, or connect Apify.
- **Apify isn't used:** the report says why (no token, token refused, monthly budget reached). After pasting the token, start a new session.
