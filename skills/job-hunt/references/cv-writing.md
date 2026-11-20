# Tailoring rules (CV + cover letter)

## The one hard rule
**Never invent.** Every bullet, skill, number, date and title in the output must trace to `profile/profile.json` (or `profile.md` for letter stories). You may: select, reorder, shorten, merge, translate, and rephrase toward the posting's vocabulary when it describes the same thing. You may not: add a skill the profile lacks, inflate a number, change a date or title, or claim seniority.

## CV (`tailored.json` = a copy of profile.json, edited)
1. Write `summary` for this job: 1–2 lines in the target language, naming the role and 2–3 matched strengths.
2. Experience: keep all entries (no gaps in the timeline); in each one, order the bullets most-relevant first and keep 2–4.
3. Projects: keep the 3–4 most relevant, in relevance order.
4. Skills: order each group most-relevant first and drop items irrelevant to the job, but keep at least 4 per group. Mirror the posting's spelling (e.g. "LLM" vs "Large Language Models") when it refers to the same thing.
5. Language: `fr` → translate every rendered string (titles of entries may stay in their original language if proper nouns). `en` → English.
6. Must fit one page: `render.py` exits 3 if not. If it does, drop the least relevant project or bullet and re-render.

## Cover letter (`letter.json`, same fields as below, in JSON)
```json-ish (write as JSON)
company: Acme
role: AI Engineer
subject: "Candidature – AI Engineer (CDI)"
greeting: "Madame, Monsieur,"            # or "Dear Hiring Team,"
paragraphs:                               # 3–4 paragraphs, ≤ 250 words total
  - Hook: why this company/role specifically (from the posting, not generic praise)
  - Proof 1: most relevant experience with a number, linked to a stated need
  - Proof 2: a project or story from profile.md, linked to another need
  - Close: availability (settings `start`), contract, call to action
closing: "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées."
date: "20 novembre 2026"                 # the template prefixes the city from contact.location
```
Tone: direct, specific, no clichés ("passionate", "dynamic", "je me permets"). French letters use vouvoiement.

## notes.md (per job)
- The job URL, score, why it was picked.
- A keyword coverage table: posting requirement → profile evidence (id) or "gap".
- A list of every rephrased bullet: `original id → new text` (this is what the reviewer checks).
