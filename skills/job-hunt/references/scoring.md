# Scoring rubric (0–100)

Score every job against `profile/profile.json` + `state/settings.json`. Use only the posting text; do not guess about the company.

| Criterion | Weight | Full marks when |
|---|---|---|
| Skills fit | 35 | Most required skills appear in the profile's skills/experience/projects |
| Seniority fit | 15 | Compare the posting's **minimum** years with the profile's level: 0–2 yrs or no stated minimum → 15; 3 yrs → 5; "confirmé"/"senior" with no number → 5 |
| Contract fit | 15 | Matches `contracts` (VIE must be explicit for VIE) |
| Location / remote fit | 10 | In a configured location and matches `remote` |
| Language fit | 10 | Required languages ⊆ profile languages at the level asked |
| Role interest | 15 | AI/ML/LLM/data/software engineering, close to the profile's headline |

**Hard zero (score 0, reason given)**: the posting requires **4 or more years minimum** ("4+ ans", "5 years", "3–5 years" → its minimum is 3, so this rule doesn't apply) while the profile's level is intern or junior; matches a dealbreaker in `preferences`, an exclusion slipped through, requires a visa/clearance the profile can't get, internship/alternance when not in `contracts`, or the description is empty.

**Bonuses** (cap at 100): +10 if the company is in `target_companies` (companies to watch), +5 if it is in `bonus_companies`. Apply `preferences` (free text) as preferences (±5) or as dealbreakers (hard zero) depending on how they are worded.

**Penalties**: −10 if it's a staffing agency with a vague client, −10 if the salary is stated below `salary_min`, −5 if there are more than 200 applicants.

Output: a JSON array with **exactly one object per input job**, in the same order. Count them before you answer; never skip a job, even an obvious zero.
`{"id": "...", "score": 0-100, "lang": "fr|en|other", "why": "≤25 words", "matched": ["skill", ...], "gaps": ["skill", ...]}`
`lang` is the posting's language: `fr`, `en`, or `other` (Korean, German, …). It drives the CV language when `cv_language: match`, and `other` means English.

Jobs come from LinkedIn (`source` missing) or from company careers sites (`source: "careers"`). Score them the same way. Careers postings often leave out the contract or seniority: infer them from the text, and don't penalise a field that's simply missing.
