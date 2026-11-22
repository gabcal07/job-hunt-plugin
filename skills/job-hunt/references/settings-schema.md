# From JOB_SEARCH.md to state/settings.json

`JOB_SEARCH.md` is free-form and written by a human. At the start of every run, the agent reads it and writes `~/job-hunt/state/settings.json` in **exactly** the shape below, then runs `scripts/settings.py --check`. Scripts only ever read settings.json.

```json
{
  "searches": [
    {"query": "AI engineer", "location": "Paris, Île-de-France, France",
     "experience": [2], "job_type": ["F"], "workplace": [1, 3],
     "posted_within_hours": 24, "why": "title × city"}
  ],
  "target_companies": ["Mistral AI"],
  "bonus_companies": ["Doctolib"],
  "exclude_words": ["senior", "lead", "staff"],
  "exclude_companies": [],
  "contracts": ["CDI", "VIE"],
  "level": "junior",
  "remote": "hybrid ok",
  "start": "2027-01",
  "salary_min": null,
  "top_n": 5,
  "min_score": 65,
  "cv_language": "match",
  "max_per_search": 15,
  "max_total": 60,
  "max_details": 20,
  "preferences": "free text from 'What I want / avoid', verbatim",
  "notes": ["anything you interpreted or could not map, in plain words"]
}
```

## Interpretation rules
- **Scope:** contract and level stated anywhere (intro text or Basics) apply to **every** job title, unless a line says otherwise.
- **Locations:** expand a bare city to LinkedIn's form: "Lyon" → "Lyon, Auvergne-Rhône-Alpes, France", "Berlin" → "Berlin, Germany". "Remote in France" → location "France" with `workplace: [2]`.
- **Searches (keep LinkedIn requests low):** one search per **city**, not per title. Its `query` OR-combines up to 5 job titles: `(AI engineer) OR (data engineer) OR (machine learning engineer)`. With more than 5 titles, add a second search for that city. Each city carries its own `workplace`: "Paris if hybrid" → [3]; "also Lyon if remote" → [2]; no condition → the global Remote value. A global "remote is great too" adds 2 to every city's list. A "Search profiles" line is its own search with its own filters. Contract words LinkedIn can't filter (alternance, VIE) go inside each title group: `(data engineer alternance) OR (data analyst alternance)`. Aim for 6 searches or fewer in total.
- **Companies to watch** (also accepted under the old heading "Target companies"): each `- Name — URL` line is one company, and the URL is optional. Put every name in `target_companies`; their careers sites are read by `careers.py` from `state/companies.json`, so they add **no** LinkedIn searches. "Companies I'm curious about" go into `bonus_companies`.
- **LinkedIn filter codes:**
  - `experience` (f_E): intern → [1], junior/entry → [2], mid → [3,4], senior → [4,5]. **alternance or stage with no level stated → [1,2]**.
  - `job_type` (f_JT): CDI/CDD/VIE/full-time → F, freelance/contract → C, temporary → T, stage/internship → I. Alternance → **both** the filter [F,I] **and** the word "alternance" in the query (LinkedIn has no alternance filter; the word does the real work). VIE has no filter either: add one "(<title 1> VIE) OR (<title 2> VIE)" search per city.
  - `workplace` (f_WT): on-site → 1, remote → 2, hybrid → 3. "hybrid ok" → [1,3]; "remote only" → [2]; no preference → [].
  - `posted_within_hours`: "1 day" → 24, "3 days" → 72, "1 week" → 168, **default 24** when not given. On Mondays the script widens 24 to 72 by itself.
- **Exclusions:** `exclude_words` are only explicit words the user quotes or lists ("senior", "lead"), matched as whole words against title and company. **Categories** ("consulting firms", "ESN", "defense industry", "startups") never become exclude words, which would remove good offers. Copy them into `preferences` as dealbreakers, and the scorer applies them by reading the posting. Never exclude a contract word the user wants.
- **preferences:** the "What I want / avoid" text verbatim, plus every wish that has no field: school rhythm, categories to avoid, visa situation, company type. Keep the user's words.
- **Numbers:** "N offers" → `top_n`. "minimum X", "even weak ones (X)" → `min_score` X. Default `min_score` is 65.
- **Dates:** `start` is "YYYY-MM"; "September 2027" → "2027-09", "asap" → the current month.
- **Caps:** `max_total` = min(150, 10 × top_n + 30). `max_per_search` = 25 (each OR search covers several titles). `max_details` = min(40, 4 × top_n) descriptions (one LinkedIn request each, best-ranked jobs first). Optional `max_requests` (default 90) caps LinkedIn requests per run; leave it out unless the user is on a home IP and wants more.
- **cv_language:** "match" (same as the offer), "en" or "fr".
- **Ambiguity:** never guess silently. Make the most reasonable reading and write it in `notes` in plain words. The run report shows `notes`, so the user can correct the file.
- **Missing required fields** (no job titles or no cities): stop and ask. In a scheduled run, report it instead.
