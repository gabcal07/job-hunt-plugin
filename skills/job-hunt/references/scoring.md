# Scoring rubric (0–100)

Score every job against `profile/profile.json` + `state/settings.json`. Use only the posting text; do not guess about the company.

| Criterion | Weight | Full marks when |
|---|---|---|
| Skills fit | 35 | Most required skills appear in the profile's skills/experience/projects |
| Seniority fit | 15 | Junior/graduate/0–2 yrs, or no stated minimum. ≥4 yrs required → 0 |
| Contract fit | 15 | Matches `contracts` (VIE must be explicit for VIE) |
| Location / remote fit | 10 | In a configured location and matches `remote` |
| Language fit | 10 | Required languages ⊆ profile languages at the level asked |
| Role interest | 15 | AI/ML/LLM/data/software engineering, close to the profile's headline |

**Hard zero (score 0, reason given)**: matches a dealbreaker in `preferences`, an exclusion slipped through, requires a visa/clearance the profile can't get, internship/alternance when not in `contract_types`, or the description is empty.

**Bonuses** (cap at 100): +10 if the company is in `target_companies`, +5 if it is in `bonus_companies`. Apply `preferences` (free text) as preferences (±5) or as dealbreakers (hard zero) depending on how they are worded.

**Penalties**: −10 if it's a staffing agency with a vague client, −10 if the salary is stated below `salary_min`, −5 if there are more than 200 applicants.

Output per job, one line in a JSON array:
`{"id": "...", "score": 0-100, "lang": "fr|en", "why": "≤25 words", "matched": ["skill", ...], "gaps": ["skill", ...]}`
`lang` is the language the posting is written in (it drives the CV language when `cv_language: match`).
