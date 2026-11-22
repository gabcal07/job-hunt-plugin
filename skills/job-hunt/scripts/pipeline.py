#!/usr/bin/env python3
"""Deterministic steps of a job-hunt run, so the model only does what needs judgement.

Stdlib only, Python 3.10+. Every command prints a short summary (never job text) so the agent's context stays small.

  pipeline.py settings-status --job-search D/JOB_SEARCH.md --settings D/state/settings.json [--stamp]
      "fresh" (exit 0) when JOB_SEARCH.md is unchanged since the last --stamp, else "stale" (exit 1).
  pipeline.py merge --run D/runs/DAY
      jobs.json + careers.json -> all.json (one entry per company+title, the company's own link wins).
  pipeline.py prepare --run D/runs/DAY --settings S.json --profile P.json [--batch 15]
      Hard zeros decided in code (auto.json), then compact batches for the scoring workers (_score/batchN.json:
      trimmed descriptions + the profile and settings fields the rubric uses). Prints the batch paths.
  pipeline.py collect --run D/runs/DAY --settings S.json
      _score/scoresN.json + auto.json -> scores.json; adds the fixed bonuses; selects top_n >= min_score;
      writes shortlist.md and selected.json; creates one folder per selected job with job.json. Exit 7 if a job
      has no score (the missing ids are printed).
  pipeline.py factcheck --profile P.json --profile-md P.md --dir RUN/<job>
      Numbers, skills, titles and dates in tailored.json / letter.json that are not in the profile. Exit 8 if any.
  pipeline.py render-all --dir RUN/<job> --lang fr [--accent "#6B1E2E"] [--heading-font serif] [--photo P]
      render.py cv (+docx) -> check -> letter, one summary line per step; exit code of the first failure.
  pipeline.py report --run D/runs/DAY
      The numbers for the run report, as one JSON object.
  pipeline.py --self-test
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is needed: install it from python.org (Windows: also `winget install Python.Python.3.12`).")
for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from linkedin_search import job_key  # noqa: E402

DESC_CAP = 2500
SHORTLIST_ROWS = 15


def load(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def save(p, o):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")


def norm(s):
    return unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode()


def jobs_of(o):
    return o.get("jobs", []) if isinstance(o, dict) else o


# ---------------------------------------------------------------- settings cache
def settings_status(a):
    h = hashlib.sha256(Path(a.job_search).read_bytes()).hexdigest()
    stamp = Path(a.settings).with_suffix(".hash")
    if a.stamp:
        stamp.write_text(h, encoding="utf-8")
        print("stamped")
        return 0
    fresh = Path(a.settings).is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == h
    print("fresh" if fresh else "stale")
    return 0 if fresh else 1


# ---------------------------------------------------------------- merge
def merge(run):
    li = jobs_of(load(run / "jobs.json", {"jobs": []}))
    ca = jobs_of(load(run / "careers.json", {"jobs": []})) + jobs_of(load(run / "wttj.json", {"jobs": []}))
    out, by_key = [], {}
    for j in ca + li:  # careers (and WTTJ) first: the company's own link wins
        k = job_key(j.get("company", ""), j.get("title", ""))
        if k in by_key:
            keep = by_key[k]
            if j.get("url") and j["url"] != keep.get("url"):
                keep.setdefault("alt_urls", []).append(j["url"])
            if len(j.get("description", "")) > len(keep.get("description", "")):
                keep["description"] = j["description"]
            continue
        j.setdefault("source", "linkedin")
        by_key[k] = j
        out.append(j)
    save(run / "all.json", {"jobs": out})
    return {"linkedin": len(li), "careers": len(ca), "merged": len(out), "duplicates": len(li) + len(ca) - len(out)}


# ---------------------------------------------------------------- hard zeros (code, not model)
_NUM = r"(\d{1,2})"
_YEARS = re.compile(
    r"(?:at least|minimum|min\.?|plus de|au moins)?\s*" + _NUM + r"\s*\+?\s*(?:(?:-|–|to|a|à)\s*" + _NUM + r"\s*\+?\s*)?"
    r"(?:years?|yrs?|ans|annees)\b")
_EXP = re.compile(r"experi|exp\b|professional|in (?:a|an|the) (?:similar|comparable)|dans (?:un|le) poste")
JUNIOR = {"intern", "internship", "stage", "junior", "entry", "graduate", "alternance", "apprentice", ""}
INTERN_WORDS = re.compile(r"\b(?:stage|stagiaire|intern|internship|alternance|alternant|apprenti|apprenticeship)\b")


def min_years(text):
    """Smallest 'N years of experience' the posting asks for (None when not stated)."""
    t, best = norm(text), None
    for m in _YEARS.finditer(t):
        ctx = t[max(0, m.start() - 70): m.end() + 70]
        if not _EXP.search(ctx):
            continue
        lo = int(m.group(1))
        if 1 <= lo <= 15:
            best = lo if best is None else min(best, lo)
    return best


def hard_zero(j, cfg):
    """A reason string when the rubric's hard-zero rules apply for sure, else None."""
    if len((j.get("description") or "").strip()) < 200:
        return "description missing or too short to judge"
    level = norm(cfg.get("level", ""))
    if any(w in level for w in JUNIOR) or not level:
        y = min_years(j["description"])
        if y and y >= 4:
            return "asks %d+ years of experience; profile level is %s" % (y, cfg.get("level") or "junior")
    contracts = {norm(c) for c in cfg.get("contracts", [])}
    if not contracts & {"stage", "internship", "alternance", "apprentissage", "intern"} and INTERN_WORDS.search(norm(j["title"])):
        return "internship/alternance, not in your contracts"
    return None


# ---------------------------------------------------------------- compact descriptions
_CUE = re.compile(r"experi|year|ans\b|require|qualif|must|profil|profile|you (?:have|bring|are)|skills?|competen|"
                  r"master|bachelor|degree|diplom|bac\s*\+|python|language|anglais|english|french|francais|korean|"
                  r"remote|hybrid|teletravail|on.?site|visa|citizen|clearance|salary|salaire|€|k€|\$|contract|cdi|cdd|"
                  r"vie\b|stage|intern|alternance|start|debut|location|based in|responsib|mission|you will|vous ")
_BOILER = re.compile(r"equal opportunit|diversity|discriminat|handicap|reasonable accommodation|privacy|gdpr|rgpd|"
                     r"cookies?|benefits? include|mutuelle|tickets? restaurant|swile|perks")


def compact(desc, cap=DESC_CAP):
    """Keep the opening and every sentence that bears on the rubric, in order, up to cap chars."""
    text = re.sub(r"\s+", " ", desc or "").strip()
    if len(text) <= cap:
        return text
    sents, seen, keep = re.split(r"(?<=[.!?;:])\s+|\s+[•·▪]\s*|\s+-\s+(?=[A-Z])", text), set(), []
    for i, s in enumerate(sents):
        k = norm(s)[:80]
        if not s or k in seen or _BOILER.search(norm(s)):
            continue
        seen.add(k)
        keep.append((0 if i < 3 else 1 if _CUE.search(norm(s)) else 2, i, s))
    out, n = [], 0
    for pri, i, s in sorted(keep):
        if n + len(s) + 1 > cap:
            if pri == 0:
                s = s[: cap - n]
            else:
                continue
        out.append((i, s))
        n += len(s) + 1
    return " ".join(s for _, s in sorted(out))


def slim_profile(p):
    pick = lambda xs, ks: [{k: x[k] for k in ks if x.get(k)} for x in xs or []]
    head = p.get("headline")
    return {"headline": head.get("en") if isinstance(head, dict) else head, "skills": p.get("skills"),
            "languages": p.get("languages"), "certifications": p.get("certifications"),
            "experience": pick(p.get("experience"), ("title", "company", "dates", "tags", "bullets")),
            "projects": pick(p.get("projects"), ("title", "tags")),
            "education": pick(p.get("education"), ("title", "school", "dates"))}


def prepare(a):
    run, cfg, prof = Path(a.run), load(a.settings), load(a.profile)
    jobs = jobs_of(load(run / "all.json"))
    auto, todo = [], []
    links = [j for j in jobs if j.get("description_unavailable")]  # e.g. SAP: title and link only, never scored
    jobs = [j for j in jobs if not j.get("description_unavailable")]
    save(run / "links_only.json", [{k: j.get(k, "") for k in ("id", "title", "company", "location", "url")} for j in links])
    for j in jobs:
        why = hard_zero(j, cfg)
        if why:
            auto.append({"id": j["id"], "score": 0, "lang": "other", "why": why, "matched": [], "gaps": [], "auto": True})
        else:
            todo.append(j)
    save(run / "auto.json", auto)
    ctx = {"profile": slim_profile(prof),
           "settings": {k: cfg.get(k) for k in ("contracts", "level", "remote", "start", "salary_min", "preferences")},
           "locations": sorted({s["location"] for s in cfg.get("searches", [])})}
    d = run / "_score"
    d.mkdir(exist_ok=True)
    for old in d.glob("*.json"):
        old.unlink()
    paths = []
    for n, i in enumerate(range(0, len(todo), a.batch), 1):
        batch = [{"id": j["id"], "title": j.get("title", ""), "company": j.get("company", ""),
                  "location": j.get("location", ""), "applicants": j.get("applicants", ""),
                  "seniority": j.get("seniority", ""), "employment_type": j.get("employment_type", ""),
                  "source": j.get("source", ""), "description": compact(j.get("description", ""))}
                 for j in todo[i: i + a.batch]]
        p = d / ("batch%d.json" % n)
        save(p, dict(ctx, jobs=batch, out=str(d / ("scores%d.json" % n))))
        paths.append(str(p))
    print(json.dumps({"jobs": len(jobs), "links_only": len(links), "auto_zero": len(auto), "to_score": len(todo), "batches": paths}))


# ---------------------------------------------------------------- collect, bonuses, selection, shortlist
def applicants_n(s):
    """'Over 200 applicants' -> 201 (more than 200), 'Be among the first 25' -> 25."""
    m = re.search(r"(\d[\d,. ]*)", s or "")
    n = int(re.sub(r"\D", "", m.group(1))) if m else 0
    return n + 1 if re.search(r"\b(?:over|plus de)\b", norm(s)) else n


def bonus(j, cfg):
    """Fixed adjustments of the rubric, in code: watched/bonus company, crowded posting."""
    co, b, notes = norm(j.get("company", "")), 0, []
    hit = lambda names: any(n and (norm(n) in co or co in norm(n)) for n in names) if co else False
    if hit(cfg.get("target_companies", [])):
        b, notes = b + 10, notes + ["+10 watched company"]
    elif hit(cfg.get("bonus_companies", [])):
        b, notes = b + 5, notes + ["+5 bonus company"]
    if applicants_n(j.get("applicants")) > 200:
        b, notes = b - 5, notes + ["-5 over 200 applicants"]
    return b, notes


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", norm(s))).strip("-")[:40] or "job"


def collect(a):
    run, cfg = Path(a.run), load(a.settings)
    jobs = {j["id"]: j for j in jobs_of(load(run / "all.json")) if not j.get("description_unavailable")}
    scores = {s["id"]: s for s in load(run / "auto.json", [])}
    for f in sorted((run / "_score").glob("scores*.json")):
        for s in load(f):
            if s.get("id") in jobs and s["id"] not in scores:
                scores[s["id"]] = s
    missing = [i for i in jobs if i not in scores]
    if missing:
        print(json.dumps({"missing": missing}))
        return 7
    for i, s in scores.items():
        if s.get("auto"):
            continue
        b, notes = bonus(jobs[i], cfg)
        s["base"] = s["score"] = max(0, min(100, int(s.get("score", 0))))
        if s["score"] > 0 and b:
            s["score"] = max(0, min(100, s["score"] + b))
            s["why"] = (s.get("why", "") + " (" + ", ".join(notes) + ")").strip()
    ranked = sorted(scores.values(), key=lambda s: -s["score"])
    save(run / "scores.json", ranked)
    sel = [s for s in ranked if s["score"] >= cfg.get("min_score", 65)][: cfg.get("top_n", 5)]
    folders = []
    for s in sel:
        j = jobs[s["id"]]
        d = run / ("%s-%s" % (slug(j.get("company")), slug(j.get("title"))))
        save(d / "job.json", dict(j, score=s["score"], lang=s.get("lang", "en"), why=s.get("why", ""),
                                  matched=s.get("matched", []), gaps=s.get("gaps", [])))
        folders.append(str(d))
    save(run / "selected.json", [{"id": s["id"], "dir": f} for s, f in zip(sel, folders)])
    write_shortlist(run, ranked, jobs, {s["id"] for s in sel})
    print(json.dumps({"scored": len(ranked), "auto_zero": sum(1 for s in ranked if s.get("auto")),
                      "selected": len(sel), "dirs": folders}))
    return 0


def cell(s):
    return str(s or "").replace("|", "/").replace("\n", " ")


def write_shortlist(run, ranked, jobs, sel):
    rows = ["| ⭐ | Score | Title | Company | City | Source | Why |", "|---|---|---|---|---|---|---|"]
    for s in ranked[:SHORTLIST_ROWS]:
        j = jobs[s["id"]]
        rows.append("| %s | %d | [%s](%s) | %s | %s | %s | %s |" % (
            "⭐" if s["id"] in sel else "", s["score"], cell(j.get("title")), j.get("url", ""), cell(j.get("company")),
            cell(j.get("location")), j.get("source", "linkedin"), cell(s.get("why"))))
    rest = len(ranked) - SHORTLIST_ROWS
    zeros = sum(1 for s in ranked if s["score"] == 0)
    tail = ["", "%d more below (in scores.json); %d scored 0." % (rest, zeros)] if rest > 0 else []
    links = load(run / "links_only.json", [])
    if links:
        tail += ["", "## Open these yourself (the site blocks automated reading, so they weren't scored)", ""]
        tail += ["- [%s](%s) · %s · %s" % (cell(l["title"]), l["url"], cell(l["company"]), cell(l["location"])) for l in links[:15]]
    (run / "shortlist.md").write_text("# Shortlist %s\n\n%d offers scored, %d selected.\n\n" % (run.name, len(ranked), len(sel))
                                      + "\n".join(rows + tail) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- factcheck (tailored CV + letter vs profile)
_NUMS = re.compile(r"\d+(?:[.,]\d+)?")


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


_GROUPED = re.compile(r"(?<=\d)[\s\u00a0\u202f,.'](?=\d{3}\b)")  # 10 511 / 10,511 / 10.511 -> 10511


def nums(t):
    return {n.replace(",", ".") for n in _NUMS.findall(_GROUPED.sub("", t))}


def factcheck(profile, profile_md, tailored, letter, job=None):
    """(errors, warnings). Errors: numbers in neither the profile nor the posting, changed dates, unknown entry ids.
    Warnings: skills whose words are not in the profile (often a translation: the model checks them)."""
    src = norm(" ".join(strings(profile)) + " " + profile_md)
    allowed = nums(src) | nums(norm(" ".join(strings(job or {}))))
    probs, warns = [], []
    texts = list(strings({k: v for k, v in tailored.items() if k not in ("contact", "skills")})) + list(strings(letter.get("paragraphs", [])))
    for t in texts:
        for n in sorted(nums(norm(t)) - allowed):
            if not re.fullmatch(r"(19|20)\d\d", n):
                probs.append("number %s not in profile or posting: %s" % (n, t[:90]))
    src_words = set(re.findall(r"[a-z0-9+#]{4,}", src))
    for g, items in (tailored.get("skills") or {}).items():
        for x in items:
            words = re.findall(r"[a-z0-9+#]{4,}", norm(x))
            if norm(x) not in src and words and not any(w in src_words or w.rstrip("s") in src_words for w in words):
                warns.append("skill not found in profile (translation?): %s" % x)
    by_id = {x.get("id"): x for k in ("experience", "education", "projects") for x in profile.get(k) or []}
    for k in ("experience", "education", "projects"):
        for x in tailored.get(k) or []:
            o = by_id.get(x.get("id"))
            if not o:
                probs.append("%s entry with unknown id: %s" % (k, x.get("title", x.get("id"))))
                continue
            dk = "date" if k == "projects" else "dates"
            if x.get(dk) and o.get(dk) and _NUMS.findall(x[dk]) != _NUMS.findall(o[dk]):
                probs.append("dates changed for %s: %s -> %s" % (x.get("id"), o[dk], x[dk]))
    return probs, warns


def do_factcheck(a):
    d = Path(a.dir)
    md = Path(a.profile_md).read_text(encoding="utf-8") if a.profile_md and Path(a.profile_md).is_file() else ""
    probs, warns = factcheck(load(a.profile), md, load(d / "tailored.json"), load(d / "letter.json", {}), load(d / "job.json", {}))
    print("\n".join(["ERROR " + p for p in probs] + ["CHECK " + w for w in warns]) or "factcheck OK")
    return 8 if probs else 0


# ---------------------------------------------------------------- render-all
def render_all(a):
    d, R = Path(a.dir), [sys.executable, str(HERE / "render.py")]
    design = ["--accent", a.accent, "--heading-font", a.heading_font] + (["--photo", a.photo] if a.photo else [])
    steps = [("cv", R + ["cv", "--profile", str(d / "tailored.json"), "--lang", a.lang, "--out", str(d / "cv.pdf")] + design + ["--docx"]),
             ("check", R + ["check", "--pdf", str(d / "cv.pdf"), "--docx", str(d / "cv.docx"), "--profile", str(d / "tailored.json"),
                            "--lang", a.lang, "--keywords-file", str(d / "notes.md")]),
             ("letter", R + ["letter", "--profile", str(d / "tailored.json"), "--letter", str(d / "letter.json"),
                             "--lang", a.lang, "--out", str(d / "cover-letter.pdf")])]
    for name, cmd in steps:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        tail = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"FAIL|MISSING|WARN|PAGES|DATE\?|coverage|error", l, re.I)]
        print("%s: %s%s" % (name, "ok" if r.returncode == 0 else "exit %d" % r.returncode, ("; " + " | ".join(tail[:6])) if tail else ""))
        if r.returncode:
            return r.returncode
    return 0


# ---------------------------------------------------------------- report
def report(run):
    li, ca = load(run / "jobs.json", {}), load(run / "careers.json", {})
    sc, sel = load(run / "scores.json", []), load(run / "selected.json", [])
    wt = load(run / "wttj.json", {})
    return {"linkedin_source": li.get("source", "guest"), "linkedin_note": li.get("note", ""),
            "apify_used_usd": li.get("apify_used_usd"), "wttj_found": len(wt.get("jobs", [])), "wttj_note": wt.get("note", ""),
            "links_only": len(load(run / "links_only.json", [])),
            "linkedin_found": len(li.get("jobs", [])), "linkedin_skipped": len(li.get("skipped", [])),
            "linkedin_blocked": li.get("blocked", False), "linkedin_cut_short": li.get("search_cut_short", False),
            "careers_found": len(ca.get("jobs", [])),
            "companies_failed": [c["name"] for c in ca.get("companies", []) if c.get("status") not in ("ok", "no_feed")],
            "companies_need_browser": [c["name"] for c in ca.get("needs_browser", [])],
            "scored": len(sc), "auto_zero": sum(1 for s in sc if s.get("auto")), "selected": [s["dir"] for s in sel]}


# ---------------------------------------------------------------- self-test
def self_test():
    import tempfile
    assert min_years("We need 5+ years of experience in Python") == 5
    assert min_years("3-5 years of professional experience") == 3
    assert min_years("Au moins 4 ans d'expérience en data") == 4
    assert min_years("Founded 20 years ago, we have 300 employees") is None
    assert min_years("Expérience : 2 ans minimum") == 2
    long = "x" * 300
    cfg = {"level": "junior", "contracts": ["CDI"]}
    assert hard_zero({"title": "AI Engineer", "description": "short"}, cfg).startswith("description")
    assert "5+" in hard_zero({"title": "AI Engineer", "description": long + " 5 years of experience required"}, cfg)
    assert hard_zero({"title": "Stage - Data Engineer", "description": long}, cfg).startswith("internship")
    assert hard_zero({"title": "Stage - Data Engineer", "description": long}, dict(cfg, contracts=["Stage"])) is None
    assert hard_zero({"title": "AI Engineer", "description": long + " 2+ years of experience"}, cfg) is None
    d = "Intro sentence one. Intro two. Intro three. " + "We sell shoes. " * 300 + "You have 2 years of Python experience. Equal opportunity employer."
    c = compact(d, 400)
    assert len(c) <= 400 and "2 years of Python" in c and "Equal opportunity" not in c and c.startswith("Intro sentence one."), c
    assert bonus({"company": "Mistral AI", "applicants": "Over 200 applicants"}, {"target_companies": ["Mistral"]})[0] == 5
    assert bonus({"company": "Acme"}, {"target_companies": ["Mistral"], "bonus_companies": ["acme"]})[0] == 5
    prof = {"skills": {"T": ["Python", "SQL"]}, "summary": "Cut costs by 40%",
            "experience": [{"id": "e1", "title": "Dev", "dates": "Jan 2025 - Jun 2025", "bullets": ["Built 3 tools"]}]}
    ok_t = {"skills": {"T": ["Python"]}, "experience": [{"id": "e1", "dates": "janv. 2025 - juin 2025", "bullets": ["Built **3** tools"]}]}
    assert factcheck(prof, "", ok_t, {"paragraphs": ["I cut costs by 40 %."]}) == ([], [])
    prof["summary"] += "; 10,511 steps"
    assert factcheck(prof, "", ok_t, {"paragraphs": ["un classeur de 10\u202f511 étapes, 70 semaines"]}, {"description": "70 weeks"}) == ([], [])
    bad, w = factcheck(prof, "", {"skills": {"T": ["Rust", "Pythons"]}, "experience": [{"id": "e1", "dates": "Jan 2024 - Jun 2025", "bullets": ["Built 7 tools"]}]},
                       {"paragraphs": ["Led 12 people"]})
    assert any("number 7 " in b for b in bad) and any("number 12 " in b for b in bad) and any("dates" in b for b in bad), bad
    assert w == ["skill not found in profile (translation?): Rust"], w
    with tempfile.TemporaryDirectory() as t:
        run = Path(t) / "2026-11-21"
        save(run / "jobs.json", {"jobs": [{"id": "1", "title": "AI Engineer (H/F)", "company": "Acme", "url": "li", "description": long},
                                          {"id": "2", "title": "Data Engineer", "company": "Beta", "url": "li2", "description": long + " 6 years of experience"}]})
        save(run / "careers.json", {"jobs": [{"id": "c1", "title": "AI engineer", "company": "Acme", "url": "own", "description": long, "source": "careers"}]})
        m = merge(run)
        assert m == {"linkedin": 2, "careers": 1, "merged": 2, "duplicates": 1}, m
        allj = jobs_of(load(run / "all.json"))
        assert allj[0]["url"] == "own" and allj[0]["alt_urls"] == ["li"], allj[0]
        sp, pp = Path(t) / "s.json", Path(t) / "p.json"
        save(sp, {"level": "junior", "contracts": ["CDI"], "searches": [{"location": "Paris"}], "target_companies": ["Acme"],
                  "min_score": 65, "top_n": 1})
        save(pp, prof)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            prepare(argparse.Namespace(run=str(run), settings=str(sp), profile=str(pp), batch=15))
        assert [s["id"] for s in load(run / "auto.json")] == ["2"]
        b = load(run / "_score" / "batch1.json")
        assert [j["id"] for j in b["jobs"]] == ["c1"] and "profile" in b and b["out"].endswith("scores1.json")
        with contextlib.redirect_stdout(io.StringIO()):
            assert collect(argparse.Namespace(run=str(run), settings=str(sp))) == 7
        save(run / "_score" / "scores1.json", [{"id": "c1", "score": 70, "lang": "en", "why": "fit"}])
        with contextlib.redirect_stdout(io.StringIO()):
            assert collect(argparse.Namespace(run=str(run), settings=str(sp))) == 0
        sc = load(run / "scores.json")
        assert sc[0]["id"] == "c1" and sc[0]["score"] == 80 and sc[0]["base"] == 70, sc
        assert (run / "acme-ai-engineer" / "job.json").is_file() and "⭐" in (run / "shortlist.md").read_text(encoding="utf-8")
        r = report(run)
        assert r["scored"] == 2 and r["auto_zero"] == 1 and len(r["selected"]) == 1, r
        js, st = Path(t) / "JOB_SEARCH.md", Path(t) / "state" / "settings.json"
        js.write_text("a", encoding="utf-8")
        save(st, {})
        ns = lambda stamp: argparse.Namespace(job_search=str(js), settings=str(st), stamp=stamp)
        with contextlib.redirect_stdout(io.StringIO()):
            assert settings_status(ns(False)) == 1 and settings_status(ns(True)) == 0 and settings_status(ns(False)) == 0
            js.write_text("b", encoding="utf-8")
            assert settings_status(ns(False)) == 1
    print("self-test OK")


def main():
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("settings-status")
    s.add_argument("--job-search", required=True)
    s.add_argument("--settings", required=True)
    s.add_argument("--stamp", action="store_true")
    for name in ("merge", "report"):
        sub.add_parser(name).add_argument("--run", required=True)
    s = sub.add_parser("prepare")
    s.add_argument("--run", required=True)
    s.add_argument("--settings", required=True)
    s.add_argument("--profile", required=True)
    s.add_argument("--batch", type=int, default=15)
    s = sub.add_parser("collect")
    s.add_argument("--run", required=True)
    s.add_argument("--settings", required=True)
    s = sub.add_parser("factcheck")
    s.add_argument("--profile", required=True)
    s.add_argument("--profile-md")
    s.add_argument("--dir", required=True)
    s = sub.add_parser("render-all")
    s.add_argument("--dir", required=True)
    s.add_argument("--lang", default="en", choices=["en", "fr"])
    s.add_argument("--accent", default="#1F3A5F")
    s.add_argument("--heading-font", default="serif", choices=["serif", "sans"])
    s.add_argument("--photo", default="")
    a = p.parse_args()
    if a.cmd == "settings-status":
        return settings_status(a)
    if a.cmd == "merge":
        print(json.dumps(merge(Path(a.run))))
    elif a.cmd == "prepare":
        prepare(a)
    elif a.cmd == "collect":
        return collect(a)
    elif a.cmd == "factcheck":
        return do_factcheck(a)
    elif a.cmd == "render-all":
        return render_all(a)
    elif a.cmd == "report":
        print(json.dumps(report(Path(a.run)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
