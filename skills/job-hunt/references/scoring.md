# Scoring rubric (0–100)

Your batch file holds `profile` (a slim copy), `settings` (contracts, level, remote, start, salary_min, preferences),
`locations` and `jobs`. Use only the posting text; don't guess about the company. Descriptions are trimmed to the
parts that matter; a missing field just isn't stated.

| Criterion | Weight | Full marks when |
|---|---|---|
| Skills fit | 35 | Most required skills appear in the profile's skills, experience bullets or project tags |
| Seniority fit | 15 | Posting's **minimum** years vs the profile's level: 0–2 yrs or none stated → 15; 3 yrs → 5; "confirmé"/"senior" with no number → 5 |
| Contract fit | 15 | Matches `contracts` (VIE must be explicit for VIE); infer it from the text when the field is empty |
| Location / remote fit | 10 | In one of `locations` and matches `remote` |
| Language fit | 10 | Required languages are in the profile at the level asked |
| Role interest | 15 | Close to the profile's headline and experience |

**Score 0, with the reason:** a dealbreaker in `preferences`, a visa or clearance the profile can't get, an
internship/alternance when it isn't in `contracts`, or 4+ years minimum for an intern/junior. (Code already removed the
obvious ones.)

**Adjust:** `preferences` worded as wishes ±5. −10 for a staffing agency with a vague client, −10 for a stated salary
below `salary_min`. Don't add company bonuses or applicant penalties: code adds those afterwards.

**Output:** write a JSON array to the file named in the batch's `out` field, **exactly one object per job, in the same
order** (count them; never skip one):
`{"id": "...", "score": 0-100, "lang": "fr|en|other", "why": "≤20 words", "matched": ["skill", ...], "gaps": ["skill", ...]}`
`lang` is the posting's language (`other` means English is used for the CV).
