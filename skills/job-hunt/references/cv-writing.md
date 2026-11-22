# Tailoring rules (CV + cover letter)

## The one hard rule
**Never invent.** Every bullet, skill, number, date and title in the output must trace to `profile/profile.json` (or `profile.md` for letter stories). You may: select, reorder, shorten, merge, translate, and rephrase toward the posting's vocabulary when it describes the same thing. You may not: add a skill the profile lacks, inflate a number, change a date or title, or claim seniority.

## ATS policy (every tailored CV)
These rules come from the research note "ATS Resume Parsing — How Applicant Tracking Systems Work" (user's vault, 2026). The note marks them as recommendations drawn from vendor and practitioner sources, not tested against a real ATS. `render.py` (default `elegant` design, single column) enforces the layout rules; you enforce the content rules.

| # | Rule | Why (note) | Enforced by |
|---|---|---|---|
| 1 | Single column, one linear text stream: no tables, text boxes or sidebars (the skills grid is CSS and `check` verifies its reading order) | "Two-column layouts merge sidebar text into the work history" | `render.py` (elegant/ats) |
| 2 | Name and contact details in the body, at the top, as text labels | Headers, footers and text boxes "can hide the name or contact details" | `render.py`, `check` |
| 3 | Standard headings, in this order: Summary, Experience, Education, Projects, Skills, Languages, Certifications (FR: Profil, Expérience professionnelle, Formation, Projets, Compétences, Langues, Certifications). Never invent a heading | Custom titles "may not map to Experience or Education, so the parser loses the section" | `render.py`, `check` |
| 4 | Standard font (Calibri/Helvetica body, Georgia headings; Arial in DOCX) at 10–12 pt, real bullets, no icons, straight quotes and hyphens | "Icon bullets turn into empty boxes. Smart quotes and long dashes can come out as junk" | `render.py` (`plain()`) |
| 5 | One date format on every entry (`Mon YYYY - Mon YYYY`) | Bad dates "break years-of-experience and timeline calculations" | `render.py` (`fmt_dates()`, exit 5) |
| 6 | **Mirror the posting's exact phrases**, and place them **inside experience or project bullets**, not only in Skills. Use "CI/CD" if the posting says CI/CD. | "The match is usually literal… keywords need to appear in context" | you, then `check --keywords-file` (≥70%) |
| 7 | Never invent experience to match a keyword, and never stuff keywords | "Do not list skills you do not have" | you, then the review |
| 8 | Deliver DOCX and PDF from the same content | "Sources disagree… test the file in the target system" | `render.py --docx` |
| 9 | Round-trip: extracted text must keep the section order, name, email, phone, dates and titles | "The closest local proxy for what a parser sees" | `render.py check` (exit 6) |
| 10 | Knockout check before writing | "A wrong or missing answer to a required question can end the application" | you (below) |

**Knockout check (before writing).** List the posting's must-haves: location or relocation, work authorisation or visa, minimum years, required degree, required certifications, required languages and level, contract and start date. For each, write in `notes.md` the profile evidence (an id), `GAP`, or `n/a (not stated)` when the posting doesn't ask for it. Every GAP goes in the shortlist's "why" and in the letter's close **only if** the profile honestly answers it (for example "available from March 2027"). Never paper over a GAP.

**Which file to upload** (`notes.md` and the shortlist): Greenhouse, Lever, Ashby, Workable or SmartRecruiters → `cv.pdf`; Workday, Taleo, SuccessFactors, iCIMS, LinkedIn Easy Apply or unknown → `cv.docx`.

## CV (`_work/tailored.json` = a copy of profile.json, edited)
1. Write `summary` for this job: 1–2 lines in the target language, naming the role and 2–3 matched strengths.
2. Experience: keep all entries (no gaps in the timeline); in each one, order the bullets most-relevant first and keep 2–4.
3. Projects: as many as fit, most relevant first. Aim for 2–3; 1 is acceptable when the experience is strong.
4. Skills: order each group most-relevant first and drop items irrelevant to the job: at most 4 groups of about 3 items, named after the offer's needs (see Design). Mirror the posting's spelling (e.g. "LLM" vs "Large Language Models") when it refers to the same thing.
5. Language: `fr` → translate every rendered string (titles of entries may stay in their original language if proper nouns). `en` → English.
6. Must fit one page at the ATS font sizes: `render.py` exits 3 if not. **Never shrink fonts or margins.** Cut in this order, re-rendering after each cut, and stop as soon as it fits:
   1. education bullets (keep each education entry: title, school and dates);
   2. the 3rd and 4th projects;
   3. experience bullets beyond 3 on the oldest roles;
   4. skills items irrelevant to the job, and certifications not asked for;
   5. the 2nd project.
7. **Non-Latin script:** in the ATS CV, write names in Latin script only ("Exchange Program at Konkuk University", not "건국대학교"). Font fallback splits the text stream when parsed. The classic design may keep the original script.
8. **Translation for `fr`:** use these fixed terms so runs stay consistent: Native → Langue maternelle; Bilingual → Bilingue; Limited working → Notions professionnelles; Micro Services → Microservices; Internship → Stage; present → présent. Write every other translation in `notes.md`.
9. **Dates:** EN `Sep 2024 - Jan 2025`; FR `sept. 2024 - janv. 2025` (lower case, French abbreviations). `render.py` normalises them.
10. The `summary` sentence is prose, so it goes through the writing pass below. Bullets don't, because they're fact-checked lines and rewriting risks changing a claim.

## Design (elegant PDF)
Pick per job and write the choice in `notes.md`:
- `--accent`: luxury, fashion, heritage → `#6B1E2E` (bordeaux) or `#1F3A5F` (navy) or `#1E4D3A` (dark green), `--heading-font serif`; tech, startups → `#1F3A5F` or `#1D5C63` (teal), `--heading-font sans`; finance, consulting, law → `#1F3A5F` or `#333F48`; industry, engineering → `#2B3A4A`; healthcare → `#1F5C8A`. If the user has a brand colour that fits the sector, use it.
- `--photo D/profile/sources/photo.jpg` for France and luxury when the profile has a professional photo on a plain light background. Omit it for US/UK offers. If the photo has a busy or coloured background, don't use it; tell the user to provide a better one.
- Skills: at most 4 groups, about 3 items each, named after the offer's needs (e.g. "Data / Cloud / Analyse / Outils"); they render as a 4-column grid and a 5th group would wrap to a second row.
- Hobbies render as "Centres d'intérêt" / "Hobbies": keep only specific, true ones (a detail beats "voyages, cinéma").

## Bullets and headline (on top of the hard rule)
- **Headline** = who the user is for this job, adapted from the offer's title and true (offer "Assistant(e) Chef de Projet Événementiel" → "Chef de projet événementiel & partenariats"). No contract type or dates in it; an alternance/stage goes in the last sentence of `summary`.
- **Summary**: 2–3 lines, the user's voice: role + sector, 2–3 proven strengths with one number, what they look for. Never copy the posting; never open with "Passionné(e)" / "Motivé(e)".
- **Order**: reverse chronological, ongoing roles first; never push the current employer down. Relevance comes from rewording and reordering bullets.
- **XYZ form**: verb + what + result/number + how (tool, method, scale), using only numbers in the profile. A number just below a round figure stays honest ("près de 6 000").
- Strong ownership verbs, varied inside one job, present tense for current roles: led, launched, built, grew, organised, negotiated, designed, coordinated, delivered (FR: piloté, organisé, coordonné, développé, négocié, conçu, déployé, rédigé). Avoid helped / supported / worked on / was responsible for / participated in.
- **Bold** the one most important result per strong bullet with `**…**` (max 1–2 per bullet, never a whole sentence). Bold renders only in the elegant PDF; the DOCX and `check` strip the markers.
- At least 3 bullets on the main roles, 4–5 on the most relevant, 2–3 on minor ones.
- CV-specific AI tells to avoid in bullets as well: every bullet starting with the same verb, identical sentence lengths, trailing "…, ensuring/fostering/enhancing X", words like spearheaded, leveraged, orchestrated, robust, seamless, pivotal, results-driven. Fix by stating the fact plainly, never by adding a detail.
- In `tailor-one` mode (the user is in the chat), you may list **likely but unlisted** experience the offer needs (inferred from the profile's roles and tools) and ask the user to confirm it; add it to `profile.json` only after a yes. In the daily run, never: unconfirmed means absent.

## Cover letter (`_work/letter.json`, same fields as below, in JSON)
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

## Writing pass (letter paragraphs and the CV summary)
After the content is written and before the fact review, rewrite **every letter paragraph and the CV summary once** with the bundled `humanizer` skill (`$S/../humanizer/SKILL.md`), in **embedded mode** (return only the final text). Rules on top of humanizer's own:
- **Never add a fact, detail, number, reason or intention** that isn't already in that paragraph, `profile.json` or `profile.md`. "I designed it to be simple because…" counts as an invented claim. If a sentence is generic, make it simpler or delete it, never more specific.
- French clichés to remove as well: "dans un monde en constante évolution", "je me permets", "passionné(e)", "non seulement… mais aussi", "riche et diversifié", "n'hésitez pas à", "incontournable", "au quotidien" used as filler.
- For **French** letters, French typography wins over humanizer's punctuation rules: keep « » (and use « » rather than curly “ ” for any quotation), the non-breaking space (U+00A0) before ; : ! ? % and inside numbers, and the formal closing formula. Removing em dashes and "ce n'est pas X mais Y" constructions still applies. `render.py` keeps these in letters and folds them to ASCII only in CVs, where ATS parsing matters more than typography.
- The `subject`, `greeting` and `closing` fields are fixed formulas and are not rewritten.
- `render.py` removes invisible characters (zero-width spaces, BOM, soft hyphens) from every CV and letter, so there's no separate scrub step.

The aim is a clearer letter in the user's voice, not hiding that AI helped: never claim the text "is human-written". If the pass can't run, keep the text as written and note `writing pass skipped: <reason>` in `notes.md`.

## notes.md (per job, at the folder root)
- The job URL, score, why it was picked.
- A keyword coverage table: posting requirement → profile evidence (id) or "gap".
- A list of every rephrased bullet: `original id → new text` (this is what the reviewer checks).
- **Knockout table**: must-have → profile evidence (id) or GAP.
- **`## Keywords`** section, written **after the final one-page render** (trimming can remove a keyword): one `- keyword` line per exact phrase copied from the posting **and actually used in the CV** (for example `- LLM`, `- CI/CD`, `- Python`), 8–15 of them, never a gap. `render.py check --keywords-file notes.md` reads only this section and needs ≥70% of them in the CV text.
- **Upload**: `cv.pdf` or `cv.docx`, and why (the ATS).
- **Writing pass**: which paragraphs the humanizer changed, as one line each.
