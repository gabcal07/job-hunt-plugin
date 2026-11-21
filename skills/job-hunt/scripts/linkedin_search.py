#!/usr/bin/env python3
"""Polite, read-only LinkedIn job collector using the public guest endpoints (no login).

Stdlib only, Python 3.10+. Paces LinkedIn requests 4-8 s apart; on 429/999/403 cools down 60 s then 180 s.
If the search phase is still blocked it waits once more and fetches descriptions for what it found
("search_cut_short": true); a block while fetching descriptions stops everything ("blocked": true).

Usage: linkedin_search.py (--settings PATH | --query Q --location L) [--max-total N] [--out FILE] [--dry-run]
"""
import argparse
import html
import itertools
import json
import re
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is needed: install it from python.org (Windows: also `winget install Python.Python.3.12`).")
for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    _s.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://www.linkedin.com/jobs-guest/jobs/api/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
BLOCK_CODES = (429, 999, 403)
RETRY_WAIT = 20
# LinkedIn rate-limits per IP: pause between requests, cool down on a block, then give up
LINKEDIN_PAUSE = (4.0, 8.0)
COOLDOWNS = (60, 180)


class Blocked(Exception):
    pass


class Grab(HTMLParser):
    """Collect text (or one attribute) of elements matching specs: name -> (tag, class substring, attr|None)."""

    def __init__(self, specs):
        super().__init__(convert_charrefs=True)
        self.specs = specs
        self.out = {n: [] for n in specs}
        self.active = []  # [name, tag, depth, parts]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for cap in self.active:
            if cap[1] == tag:
                cap[2] += 1
            elif tag in ("br", "p", "li", "div"):
                cap[3].append(" ")
        cls = a.get("class") or ""
        for name, (stag, scls, sattr) in self.specs.items():
            if tag == stag and scls in cls:
                if sattr:
                    if a.get(sattr):
                        self.out[name].append(a[sattr])
                elif not any(c[0] == name for c in self.active):
                    self.active.append([name, tag, 1, []])

    def handle_data(self, data):
        for cap in self.active:
            cap[3].append(data)

    def handle_endtag(self, tag):
        for cap in list(self.active):
            if cap[1] == tag:
                cap[2] -= 1
                if cap[2] == 0:
                    self.out[cap[0]].append(" ".join("".join(cap[3]).split()))
                    self.active.remove(cap)


def grab(html_text, specs):
    p = Grab(specs)
    p.feed(html_text)
    p.close()
    return p.out


CARD_SPECS = {
    "title": ("h3", "base-search-card__title", None),
    "company": ("h4", "base-search-card__subtitle", None),
    "location": ("span", "job-search-card__location", None),
    "posted": ("time", "", "datetime"),
    "url": ("a", "base-card__full-link", "href"),
}
DETAIL_SPECS = {
    "description": ("div", "show-more-less-html__markup", None),
    "crit_h": ("h3", "description__job-criteria-subheader", None),
    "crit_v": ("span", "description__job-criteria-text", None),
    "applicants": ("figcaption", "num-applicants__caption", None),
    "applicants2": ("span", "num-applicants__caption", None),
}
URN = 'data-entity-urn="urn:li:jobPosting:'


def parse_cards(html_text):
    cards = []
    for chunk in html_text.split(URN)[1:]:
        jid = chunk.split('"', 1)[0]
        if not jid.isdigit():
            continue
        o = grab(chunk, CARD_SPECS)
        first = lambda k: (o[k][0] if o[k] else "")
        url = first("url").split("?", 1)[0] or "https://www.linkedin.com/jobs/view/" + jid
        cards.append({"id": jid, "url": url, "title": first("title"), "company": first("company"),
                      "location": first("location"), "posted": first("posted")})
    return cards


def parse_detail(html_text):
    o = grab(html_text, DETAIL_SPECS)
    crit = {h.lower(): v for h, v in zip(o["crit_h"], o["crit_v"])}
    app = (o["applicants"] or o["applicants2"] or [""])[0]
    return {
        "seniority": crit.get("seniority level", ""),
        "employment_type": crit.get("employment type", ""),
        "job_function": crit.get("job function", ""),
        "industries": crit.get("industries", ""),
        "applicants": app,
        "description": o["description"][0] if o["description"] else "",
    }


class Client:
    def __init__(self, pause=(1.5, 3.5), cooldowns=(RETRY_WAIT,)):
        self.last, self.pause, self.cooldowns = False, pause, cooldowns

    def get(self, url, accept=None):
        if self.last:
            time.sleep(random.uniform(*self.pause))
        self.last = True
        hops, attempt = 0, 0
        while True:
            try:
                req = urllib.request.Request(url, headers=dict(HEADERS, Accept=accept) if accept else HEADERS)
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 308 and e.headers.get("Location") and hops < 5:  # py3.9 urllib does not follow 308
                    url, hops = urllib.parse.urljoin(url, e.headers["Location"]), hops + 1
                    continue
                if e.code not in BLOCK_CODES:
                    if e.code == 404:
                        return ""
                    raise
                if attempt >= len(self.cooldowns):
                    raise Blocked("HTTP %d after %d cool-downs" % (e.code, attempt))
                wait = self.cooldowns[attempt]
                print("warning: HTTP %d, cooling down %ds then retrying" % (e.code, wait), file=sys.stderr)
                time.sleep(wait)
                attempt += 1


def hours(h):
    """Monday: widen 24h to 72h so the weekend is covered."""
    return 72 if h == 24 and date.today().weekday() == 0 else h


def search_url(s, start):
    p = {"keywords": s["query"], "location": s["location"], "start": start}
    if s.get("posted_within_hours"):
        p["f_TPR"] = "r%d" % (hours(s["posted_within_hours"]) * 3600)
    for k, v in (("f_E", s.get("experience")), ("f_JT", s.get("job_type")), ("f_WT", s.get("workplace"))):
        if v:
            p[k] = ",".join(map(str, v))
    return BASE + "seeMoreJobPostings/search?" + urllib.parse.urlencode(p)


def is_target(company, targets):
    c = company.lower()
    return bool(c) and any(t.lower() in c or c in t.lower() for t in targets if t)


def build_searches(a, cfg):
    """List of search dicts (query, location, experience, job_type, workplace, posted_within_hours, why).
    CLI filter flags override every search's own value."""
    csv = lambda v: [x for x in v.split(",") if x] if v else None
    over = {"experience": csv(a.experience), "job_type": csv(a.job_type), "workplace": csv(a.workplace),
            "posted_within_hours": a.posted_within_hours}
    out = [dict(x) for x in cfg.get("searches", [])]
    out += [{"query": q, "location": l, "why": "cli"} for q in a.query for l in a.location]
    for x in out:
        x.update({k: v for k, v in over.items() if v})
    return out


def run(a, cfg, specs):
    seen = {}
    if a.seen:
        try:
            with open(a.seen, encoding="utf-8") as f:
                seen = json.load(f)
        except FileNotFoundError:
            pass
    cli = Client(LINKEDIN_PAUSE, COOLDOWNS)
    searches, per_search, ids, blocked, search_cut = [], [], set(), False, False
    excl_kw = [k.lower() for k in a.exclude_keyword]
    excl_co = [c.lower() for c in a.exclude_company]
    targets = cfg.get("target_companies", [])

    # whole-word match on title+company only: descriptions mention "senior"/"lead"/"stage" too often; scoring handles them
    excl_re = re.compile(r"\b(" + "|".join(re.escape(k) for k in excl_kw) + r")\b") if excl_kw else None

    def excluded(j):
        text = (j["title"] + " " + j["company"]).lower()
        return bool(excl_re and excl_re.search(text)) or any(c in j["company"].lower() for c in excl_co)

    try:
        for s in specs:
            found, kept, start = 0, [], 0
            why = s.get("why") or s["query"]
            searches.append({"query": s["query"], "location": s["location"], "why": why, "found": 0})
            per_search.append(kept)
            while found < a.max_per_search:
                cards = parse_cards(cli.get(search_url(s, start)))
                if not cards:
                    break
                for c in cards[: a.max_per_search - found]:
                    found += 1
                    if c["id"] in ids or c["id"] in seen or excluded(c):
                        continue
                    ids.add(c["id"])
                    c["search_why"] = why
                    c["target_company"] = is_target(c["company"], targets)
                    kept.append(c)
                start += 10
            searches[-1]["found"] = found
    except Blocked as e:
        blocked = True
        print("WARNING: LinkedIn blocked the search (%s). Keeping the results so far." % e, file=sys.stderr)

    # interleave searches so max-total does not starve later ones
    jobs = [j for j in itertools.chain.from_iterable(itertools.zip_longest(*per_search)) if j][: a.max_total]
    if not a.no_details:
        if blocked:  # search was cut short: cool down once, then still try the descriptions we need
            print("cooling down %ds before fetching descriptions" % COOLDOWNS[-1], file=sys.stderr)
            time.sleep(COOLDOWNS[-1])
            blocked, search_cut = False, True
        try:
            for j in jobs:
                j.update(parse_detail(cli.get(BASE + "jobPosting/" + j["id"])))
        except Blocked as e:
            blocked = True
            print("WARNING: LinkedIn blocked us (%s). Stopping all requests; keeping what was gathered." % e, file=sys.stderr)
    for j in jobs:
        for k in ("seniority", "employment_type", "job_function", "industries", "applicants", "description"):
            j.setdefault(k, "")

    if a.seen and not a.dry_run:
        today = date.today().isoformat()
        for j in jobs:
            seen.setdefault(j["id"], today)
        with open(a.seen, "w", encoding="utf-8") as f:
            json.dump(seen, f, indent=1)

    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "blocked": blocked, "search_cut_short": search_cut,
            "searches": searches, "jobs": jobs}


SAMPLE_CARD = """<ul><li><div class="base-card base-search-card" data-entity-urn="urn:li:jobPosting:123456">
<a class="base-card__full-link" href="https://fr.linkedin.com/jobs/view/ml-engineer-123456?trk=x&amp;y=1"></a>
<div class="base-search-card__info"><h3 class="base-search-card__title"> ML Engineer </h3>
<h4 class="base-search-card__subtitle"><a class="hidden-nested-link" href="#">Acme &amp; Co</a></h4>
<div class="base-search-card__metadata"><span class="job-search-card__location">Paris, France</span>
<time class="job-search-card__listdate" datetime="2026-11-19">1 day ago</time></div></div></div></li></ul>"""
SAMPLE_DETAIL = """<div><figcaption class="num-applicants__caption">Be among the first 25 applicants</figcaption>
<div class="show-more-less-html__markup"><p>Build <strong>models</strong>.<br>Ship them.</p><ul><li>Python</li></ul></div>
<ul><li class="description__job-criteria-item"><h3 class="description__job-criteria-subheader">Seniority level</h3>
<span class="description__job-criteria-text description__job-criteria-text--criteria">Entry level</span></li>
<li class="description__job-criteria-item"><h3 class="description__job-criteria-subheader">Employment type</h3>
<span class="description__job-criteria-text">Full-time</span></li></ul></div>"""


def self_test():
    (c,) = parse_cards(SAMPLE_CARD)
    assert c == {"id": "123456", "url": "https://fr.linkedin.com/jobs/view/ml-engineer-123456", "title": "ML Engineer",
                 "company": "Acme & Co", "location": "Paris, France", "posted": "2026-11-19"}, c
    d = parse_detail(SAMPLE_DETAIL)
    assert d["description"] == "Build models. Ship them. Python", d["description"]
    assert d["seniority"] == "Entry level" and d["employment_type"] == "Full-time", d
    assert d["applicants"] == "Be among the first 25 applicants", d
    assert d["industries"] == "" and d["job_function"] == ""
    assert is_target("Mistral AI", ["mistral"]) and is_target("Mistral", ["Mistral AI"])
    assert not is_target("Acme", ["Mistral AI"]) and not is_target("", ["x"])
    s = {"query": "q", "location": "Paris", "experience": [2, 3], "workplace": [1, 3]}
    assert "f_E=2%2C3" in search_url(s, 0) and "f_WT=1%2C3" in search_url(s, 0) and "f_TPR" not in search_url(s, 0)
    assert "f_TPR=r259200" in search_url(dict(s, posted_within_hours=72), 0)
    a = argparse.Namespace(query=["x"], location=["Lyon"], experience="1", job_type=None, workplace=None,
                           posted_within_hours=None)
    bs = build_searches(a, {"searches": [dict(s)]})
    assert [x["experience"] for x in bs] == [["1"], ["1"]] and bs[0]["workplace"] == [1, 3] and bs[1]["why"] == "cli", bs
    print("self-test OK")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", action="append", default=[])
    p.add_argument("--location", action="append", default=[])
    p.add_argument("--posted-within-hours", type=int)
    p.add_argument("--experience", help="f_E, e.g. 2,3")
    p.add_argument("--job-type", help="f_JT, e.g. F")
    p.add_argument("--workplace", help="f_WT, e.g. 1,3")
    p.add_argument("--settings", help="settings.json (see references/settings-schema.md); flags below override it")
    p.add_argument("--max-per-search", type=int, help="default 25, or the file's value")
    p.add_argument("--max-total", type=int, help="default 60, or the file's value")
    p.add_argument("--exclude-keyword", action="append", default=[])
    p.add_argument("--exclude-company", action="append", default=[])
    p.add_argument("--seen", help="JSON file id -> first_seen date")
    p.add_argument("--no-details", action="store_true")
    p.add_argument("--out")
    p.add_argument("--dry-run", action="store_true", help="do not update the seen file")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--job-url", help="fetch one LinkedIn job (URL or id) and exit")
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if a.job_url:
        m = re.search(r"(\d{8,})", a.job_url)
        if not m:
            p.error("--job-url: no LinkedIn job id found in %r" % a.job_url)
        jid = m.group(1)
        job = {"id": jid, "url": "https://www.linkedin.com/jobs/view/" + jid}
        page = Client(LINKEDIN_PAUSE, COOLDOWNS).get(BASE + "jobPosting/" + jid)
        job.update(parse_detail(page))
        # shortcut: top-card regexes for the one-off mode only; search mode gets these from cards
        for k, rx in (("title", r'topcard__title[^>]*>([^<]+)'), ("company", r'topcard__org-name-link[^>]*>\s*([^<]+)'),
                      ("location", r'topcard__flavor--bullet">\s*([^<]+)')):
            mm = re.search(rx, page)
            job[k] = html.unescape(mm.group(1)).strip() if mm else ""
        out = json.dumps({"jobs": [job]}, ensure_ascii=False, indent=1)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(out)
        else:
            print(out)
        return
    cfg = {}
    if a.settings:
        with open(a.settings, encoding="utf-8") as f:
            cfg = json.load(f)
    elif not a.query or not a.location:
        p.error("need --settings, or at least one --query and one --location")
    for flag, key, dflt in (("max_per_search", "max_per_search", 25), ("max_total", "max_total", 60)):
        if getattr(a, flag) is None:
            setattr(a, flag, cfg.get(key, dflt))
    a.exclude_keyword = a.exclude_keyword or cfg.get("exclude_words", [])
    a.exclude_company = a.exclude_company or cfg.get("exclude_companies", [])
    specs = build_searches(a, cfg)
    if not specs:
        p.error("no searches to run")
    res = run(a, cfg, specs)
    text = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
