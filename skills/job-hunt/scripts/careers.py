#!/usr/bin/env python3
"""Read company careers sites through their job platform's public JSON API (no login).

Stdlib only, Python 3.9+. Reuses the polite Client of linkedin_search.py.

Usage:
  careers.py detect URL [--name COMPANY]
  careers.py fetch --companies companies.json --settings settings.json [--seen seen.json] --out careers.json [--dry-run]
  careers.py --self-test
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.parse
from datetime import date, datetime, timezone
if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is needed: install it from python.org (Windows: also `winget install Python.Python.3.12`).")
for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    _s.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkedin_search import Blocked, Client, job_key  # noqa: E402

JSON = "application/json"
REMOTE_WORDS = ("remote", "télétravail", "teletravail", "anywhere")
CONTRACT_WORDS = {"alternance", "vie", "stage", "cdi"}
# synonym groups: any term of a group counts as the others (matched on accent-stripped lowercase text)
SYNONYMS = [("ai", "ia"), ("ml", "machine learning"), ("engineer", "ingenieur")]
NO_TOKEN = {"www", "api", "careers", "jobs", "app", "support", "help", "blog", "status"}  # not a recruitee board name


# ---------- detection ----------

# Amazon's search.json ignores loc_query; only country=<ISO3> filters (checked 2026-11-21)
COUNTRY_ISO3 = {"france": "FRA", "south korea": "KOR", "korea": "KOR", "germany": "DEU", "united kingdom": "GBR", "uk": "GBR",
                "spain": "ESP", "italy": "ITA", "netherlands": "NLD", "belgium": "BEL", "switzerland": "CHE", "ireland": "IRL",
                "luxembourg": "LUX", "japan": "JPN", "singapore": "SGP", "united states": "USA", "usa": "USA", "canada": "CAN",
                "portugal": "PRT", "poland": "POL", "sweden": "SWE", "india": "IND"}


def amazon_url(query, country="", offset=0):
    p = [("base_query", query), ("result_limit", 100), ("offset", offset)] + ([("country", country)] if country else [])
    return "https://www.amazon.jobs/en/search.json?" + urllib.parse.urlencode(p)


def feed_for(platform, token, eu=False, careers_url=None):
    if platform == "amazon":  # token = the search query; the careers URL's location rides along in the feed URL
        q = urllib.parse.parse_qs(urllib.parse.urlparse(careers_url or "").query)
        return amazon_url(token)
    return {
        "greenhouse": "https://boards-api.greenhouse.io/v1/boards/%s/jobs?content=true",
        "lever": "https://api.%slever.co/v0/postings/%%s?mode=json" % ("eu." if eu else ""),
        "ashby": "https://api.ashbyhq.com/posting-api/job-board/%s?includeCompensation=false",
        "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/%s/postings?limit=100",
        "workable": "https://apply.workable.com/api/v1/widget/accounts/%s?details=true",
        "recruitee": "https://%s.recruitee.com/api/offers/",
    }[platform] % token


def detect_url(url):
    """(platform, token, eu) from a board or API URL; ("other", None, False) when unknown."""
    u = urllib.parse.urlparse(url if "//" in url else "//" + url)
    host, parts = (u.hostname or "").lower(), [x for x in u.path.split("/") if x]
    q = urllib.parse.parse_qs(u.query)
    first = parts[0] if parts else None
    if host == "amazon.jobs" or host.endswith(".amazon.jobs"):
        return "amazon", (q.get("base_query") or [""])[0], False
    if re.fullmatch(r"(job-)?boards(\.eu)?\.greenhouse\.io", host):
        t = (q.get("for") or [None])[0] if first == "embed" else first
        return ("greenhouse", t, False) if t else ("other", None, False)
    if host == "boards-api.greenhouse.io" and len(parts) >= 3 and parts[:2] == ["v1", "boards"]:
        return "greenhouse", parts[2], False
    if re.fullmatch(r"(jobs|api)(\.eu)?\.lever\.co", host):
        eu = ".eu." in host
        if host.startswith("api"):
            return ("lever", parts[2], eu) if len(parts) >= 3 and parts[:2] == ["v0", "postings"] else ("other", None, False)
        return ("lever", first, eu) if first else ("other", None, False)
    if host == "jobs.ashbyhq.com" and first:
        return "ashby", first, False
    if host == "api.ashbyhq.com" and len(parts) >= 3 and parts[:2] == ["posting-api", "job-board"]:
        return "ashby", parts[2], False
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and first:
        return "smartrecruiters", first, False
    if host == "api.smartrecruiters.com" and len(parts) >= 3 and parts[:2] == ["v1", "companies"]:
        return "smartrecruiters", parts[2], False
    if host == "apply.workable.com":
        if len(parts) >= 5 and parts[:3] == ["api", "v1", "widget"]:
            return "workable", parts[4], False
        if first and first != "api":
            return "workable", first, False
    m = re.fullmatch(r"([a-z0-9-]+)\.recruitee\.com", host)
    if m and m.group(1) not in NO_TOKEN:
        return "recruitee", m.group(1), False
    return "other", None, False


def token_candidates(name, url):
    """Board tokens to guess: the company name squashed / dashed, then the URL's host label (www.coupang.jobs -> coupang)."""
    n = " ".join((name or "").lower().split())
    labels = (urllib.parse.urlparse(url if "//" in url else "//" + url).hostname or "").lower().split(".")
    while len(labels) > 1 and labels[0] in ("www", "careers", "jobs"):
        labels.pop(0)
    out = []
    for t in (n.replace(" ", ""), n.replace(" ", "-"), labels[0] if len(labels) > 1 else ""):
        if t and t not in out:
            out.append(t)
    return out


def probe_boards(cands, cli, limit=8):
    """First (platform, token, eu) whose public feed answers 200 with at least one job; at most `limit` requests."""
    n = 0
    for t in cands:
        for plat, eu in (("greenhouse", False), ("ashby", False), ("lever", False), ("lever", True)):
            if n >= limit:
                return None
            n += 1
            try:
                d = json.loads(cli.get(feed_for(plat, t, eu).replace("?content=true", ""), accept=JSON) or "null")
            except Exception:
                continue
            if (d.get("jobs") if isinstance(d, dict) else d):
                return plat, t, eu
    return None


def detect(url, client=None, name=""):
    plat, tok, eu = detect_url(url)
    cli = client or Client()
    if plat == "other":
        try:  # look for an embedded or linked board in the careers page itself
            page = cli.get(url, accept="text/html")
        except Exception as e:
            print("warning: could not fetch %s: %s" % (url, e), file=sys.stderr)
            page = ""
        for cand in re.findall(r"https?:(?:\\*/){2}[^\s\"'<>)]+", page):
            p2, t2, e2 = detect_url(re.sub(r"\\+/", "/", cand).replace("&amp;", "&"))
            if p2 != "other":
                plat, tok, eu = p2, t2, e2
                break
        if plat == "other" and "gh_jid" in page:  # job links carry gh_jid: the board token is named somewhere in the page
            m = re.search(r"(?:job-)?boards\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([\w-]+)", page)
            if m and m.group(1) != "embed":
                plat, tok = "greenhouse", m.group(1)
        if plat == "other":  # page blocked or empty: guess the board from the company name
            found = probe_boards(token_candidates(name, url), cli)
            if found:
                plat, tok, eu = found
    return {"platform": plat, "token": tok, "feed_url": feed_for(plat, tok, eu, url) if tok is not None else None,
            "careers_url": url}


# ---------- normalisation ----------

def clean(h, escaped=False):
    """HTML (optionally HTML-escaped HTML) -> plain text with normalised whitespace."""
    import html
    h = html.unescape(h or "") if escaped else (h or "")
    h = re.sub(r"</?(?:b|strong|i|em|u|span|a|code)\b[^>]*>", "", h)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())


def day(v):
    """ISO string or epoch milliseconds -> YYYY-MM-DD ('' when unknown)."""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, timezone.utc).strftime("%Y-%m-%d")
    return str(v or "")[:10]


def job(plat, tok, jid, url, title, loc, posted, desc):
    return {"id": "%s:%s:%s" % (plat, tok, jid), "url": url or "", "title": (title or "").strip(), "company": "",
            "location": " ".join((loc or "").split()), "posted": posted, "description": desc, "source": "careers",
            "platform": plat}


def with_remote(loc, remote):
    return (loc + ", Remote" if loc else "Remote") if remote and "remote" not in (loc or "").lower() else loc


def n_greenhouse(d, t):
    return [job("greenhouse", t, j["id"], j.get("absolute_url"), j.get("title"), (j.get("location") or {}).get("name"),
                day(j.get("updated_at")), clean(j.get("content"), escaped=True)) for j in d.get("jobs", [])]


def n_lever(d, t):
    out = []
    for j in d if isinstance(d, list) else []:
        desc = [j.get("descriptionPlain") or clean(j.get("description"))]
        desc += [x.get("text", "") + " " + clean(x.get("content")) for x in j.get("lists") or []]
        desc.append(j.get("additionalPlain") or "")
        loc = with_remote((j.get("categories") or {}).get("location"), j.get("workplaceType") == "remote")
        out.append(job("lever", t, j["id"], j.get("hostedUrl"), j.get("text"), loc, day(j.get("createdAt")),
                       " ".join(" ".join(desc).split())))
    return out


def n_ashby(d, t):
    return [job("ashby", t, j["id"], j.get("jobUrl"), j.get("title"), with_remote(j.get("location"), j.get("isRemote")),
                day(j.get("publishedAt")), " ".join((j.get("descriptionPlain") or clean(j.get("descriptionHtml"))).split()))
            for j in d.get("jobs", [])]


def n_smartrecruiters(d, t):
    out = []
    for j in d.get("content", []):
        l = j.get("location") or {}
        loc = with_remote(", ".join(x for x in (l.get("city"), (l.get("country") or "").upper()) if x), l.get("remote"))
        x = job("smartrecruiters", t, j["id"], "https://jobs.smartrecruiters.com/%s/%s" % (t, j["id"]), j.get("name"),
                loc, day(j.get("releasedDate")), "")
        x["_detail"] = "https://api.smartrecruiters.com/v1/companies/%s/postings/%s" % (t, j["id"])
        out.append(x)
    return out


def smartrecruiters_description(d):
    secs = ((d.get("jobAd") or {}).get("sections")) or {}
    return " ".join(clean((v or {}).get("text")) for v in secs.values()).strip()


def n_workable(d, t):
    return [job("workable", t, j["shortcode"], j.get("url"), j.get("title"),
                with_remote(", ".join(x for x in (j.get("city"), j.get("country")) if x), j.get("telecommuting")),
                day(j.get("published_on")), clean(j.get("description"))) for j in d.get("jobs", [])]


def n_recruitee(d, t):
    return [job("recruitee", t, j["id"], j.get("careers_url"), j.get("title"),
                with_remote(j.get("location"), j.get("remote")), day(j.get("published_at")),
                clean((j.get("description") or "") + " " + (j.get("requirements") or ""))) for j in d.get("offers", [])]


def n_amazon(d, t):
    out = []
    for j in d.get("jobs", []):
        try:
            posted = datetime.strptime(j.get("posted_date") or "", "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            posted = ""
        desc = clean(" ".join(j.get(k) or "" for k in ("description", "basic_qualifications", "preferred_qualifications")))
        out.append(job("amazon", t, j["id_icims"], "https://www.amazon.jobs" + (j.get("job_path") or ""), j.get("title"),
                       j.get("normalized_location") or j.get("location"), posted, desc))
    return out


NORMALISE = {"greenhouse": n_greenhouse, "lever": n_lever, "ashby": n_ashby, "smartrecruiters": n_smartrecruiters,
             "workable": n_workable, "recruitee": n_recruitee, "amazon": n_amazon}


# ---------- filters ----------

def norm(s):
    return unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode()


def term_in(term, text):
    """Whole-word (optional plural s) match of one term or its synonyms in accent-stripped text."""
    group = next((g for g in SYNONYMS if term in g), (term,))
    return any(re.search(r"\b%ss?\b" % re.escape(g), text) for g in group)


def keyword_groups(cfg):
    """One word list per search query, minus company names (target_companies) and contract words.
    Rule: a title matches when ALL words of at least one query occur in it (synonyms allowed: AI/IA,
    ML/machine learning, engineer/ingenieur). Queries left with no words are ignored."""
    groups = []
    for s in cfg.get("searches", []):
        # "(AI engineer) OR (data engineer)" is several titles: each parenthesised part is its own group
        for q in re.findall(r"\(([^()]*)\)", s["query"]) or [s["query"]]:
            q = norm(q)
            for c in cfg.get("target_companies", []):
                q = q.replace(norm(c), " ")
            q = q.replace("machine learning", "ml")
            words = [w for w in re.findall(r"\w+", q) if w not in CONTRACT_WORDS and w != "or"]
            if words and words not in groups:
                groups.append(words)
    return groups


def title_ok(title, groups):
    t = norm(title)
    return not groups or any(all(term_in(w, t) for w in g) for g in groups)


def location_ok(loc, cfg):
    if not loc.strip():
        return True
    l = norm(loc)
    cities = [norm(s["location"].split(",")[0]).strip() for s in cfg.get("searches", [])]
    return any(c and c in l for c in cities) or any(norm(w) in l for w in REMOTE_WORDS)


def excluded(j, cfg):
    words = [norm(w) for w in cfg.get("exclude_words", []) if w]
    if words and re.search(r"\b(%s)\b" % "|".join(re.escape(w) for w in words), norm(j["title"])):
        return True
    return any(c and norm(c) in norm(j["company"]) for c in cfg.get("exclude_companies", []))


# ---------- fetch ----------

def fetch_company(co, clients, blocked, cfg):
    """Return normalised (unfiltered) jobs for one company."""
    plat, tok, eu = detect_url(co["feed_url"])
    if plat == "other":
        plat = co.get("platform") or "other"
    if plat not in NORMALISE or tok is None:
        raise ValueError("unsupported feed_url %s" % co["feed_url"])
    host = urllib.parse.urlparse(co["feed_url"]).hostname
    if host in blocked:
        raise Blocked("host %s blocked earlier in this run" % host)
    cli = clients.setdefault(host, Client())

    def get_json(url):
        try:
            text = cli.get(url, accept=JSON)
        except Blocked:
            blocked.add(urllib.parse.urlparse(url).hostname)
            raise
        if not text:
            raise ValueError("HTTP 404 for %s" % url)
        return json.loads(text)

    if plat == "amazon":  # one search per configured country, merged by job id, paged up to 300 each
        countries = list(dict.fromkeys(COUNTRY_ISO3.get(s.get("location", "").split(",")[-1].strip().lower(), "")
                                       for s in cfg.get("searches", [])))
        countries = [c for c in countries if c] or [""]  # unknown country: unfiltered, location_ok still filters
        merged = {}
        for city in countries:
            part = []
            while len(part) < 300:
                data = get_json(amazon_url(tok, city, len(part)))
                more = NORMALISE[plat](data, tok)
                part += more
                if not more or len(part) >= data.get("hits", 0):
                    break
            merged.update((j["id"], j) for j in part)
        return list(merged.values()), get_json
    data = get_json(co["feed_url"])
    jobs = NORMALISE[plat](data, tok)
    if plat == "smartrecruiters":  # paginate (100 per page, small cap)
        while len(jobs) < data.get("totalFound", 0) and len(jobs) < 500:
            more = NORMALISE[plat](get_json(co["feed_url"] + "&offset=%d" % len(jobs)), tok)
            if not more:
                break
            jobs += more
    return jobs, get_json


def run_fetch(a):
    with open(a.companies, encoding="utf-8") as f:
        companies = json.load(f)
    with open(a.settings, encoding="utf-8") as f:
        cfg = json.load(f)
    seen = {}
    if a.seen and os.path.exists(a.seen):
        with open(a.seen, encoding="utf-8") as f:
            seen = json.load(f)
    groups, today = keyword_groups(cfg), date.today().isoformat()
    clients, blocked, out_jobs, needs_browser, report = {}, set(), [], [], []
    for co in companies:
        name = co.get("name", "")
        if not co.get("feed_url") or co.get("platform") == "other":
            needs_browser.append({"name": name, "careers_url": co.get("careers_url")})
            co.update(status="no_feed", note="no JSON feed, needs a browser", last_checked=today)
            report.append({"name": name, "status": "no_feed", "found": 0, "kept": 0})
            continue
        found, kept = 0, []
        try:
            jobs, get_json = fetch_company(co, clients, blocked, cfg)
            found = len(jobs)
            for j in jobs:
                j["company"] = name
                if (j["id"] in seen or job_key(name, j["title"]) in seen or not title_ok(j["title"], groups) or not location_ok(j["location"], cfg)
                        or excluded(j, cfg)):
                    continue
                if j.get("_detail"):  # description only for jobs that passed the filters
                    try:
                        j["description"] = smartrecruiters_description(get_json(j["_detail"]))
                    except Blocked:
                        raise
                    except Exception as e:
                        print("warning: detail failed for %s: %s" % (j["id"], e), file=sys.stderr)
                j.pop("_detail", None)
                kept.append(j)
            status, note = "ok", ""
        except Exception as e:  # one company failing never stops the others
            status, note = "failed", "%s: %s" % (type(e).__name__, e)
            print("warning: %s: %s" % (name, note), file=sys.stderr)
        out_jobs += kept
        co.update(status=status, note=note, last_checked=today, last_count=len(kept))
        report.append({"name": name, "status": status, "found": found, "kept": len(kept)})
    if not a.dry_run:
        with open(a.companies, "w", encoding="utf-8") as f:
            json.dump(companies, f, ensure_ascii=False, indent=1)
        if a.seen:
            for j in out_jobs:
                seen.setdefault(j["id"], today)
                seen.setdefault(job_key(j["company"], j["title"]), today)
            with open(a.seen, "w", encoding="utf-8") as f:
                json.dump(seen, f, indent=1)
    res = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "jobs": out_jobs,
           "needs_browser": needs_browser, "companies": report}
    text = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


# ---------- self-test ----------

def self_test():
    for url, plat, tok in (
        ("https://boards.greenhouse.io/datadog", "greenhouse", "datadog"),
        ("https://job-boards.greenhouse.io/acme/jobs/123", "greenhouse", "acme"),
        ("https://boards.greenhouse.io/embed/job_board?for=zed", "greenhouse", "zed"),
        ("https://boards-api.greenhouse.io/v1/boards/foo/jobs", "greenhouse", "foo"),
        ("https://jobs.lever.co/mistral", "lever", "mistral"),
        ("https://jobs.ashbyhq.com/ElevenLabs", "ashby", "ElevenLabs"),
        ("https://jobs.smartrecruiters.com/Acme", "smartrecruiters", "Acme"),
        ("https://careers.smartrecruiters.com/Acme/", "smartrecruiters", "Acme"),
        ("https://apply.workable.com/acme/", "workable", "acme"),
        ("https://acme.recruitee.com/", "recruitee", "acme"),
        ("https://acme.wd3.myworkdayjobs.com/en-US/External", "other", None),
        ("https://careers.doctolib.com", "other", None),
    ):
        got = detect_url(url)[:2]
        assert got == (plat, tok), (url, got)
    assert feed_for("lever", "m", True) == "https://api.eu.lever.co/v0/postings/m?mode=json"
    assert detect_url("https://api.lever.co/v0/postings/mistral?mode=json")[:2] == ("lever", "mistral")

    def one(plat, data, tok="t"):
        (j,) = NORMALISE[plat](data, tok)
        assert j["source"] == "careers" and j["platform"] == plat and j["id"].startswith("%s:%s:" % (plat, tok)), j
        return j

    j = one("greenhouse", {"jobs": [{"id": 1, "title": "ML Engineer", "absolute_url": "https://x/1", "updated_at":
            "2026-11-10T10:00:00-05:00", "location": {"name": "Paris"}, "content": "&lt;p&gt;Build &lt;b&gt;things&lt;/b&gt; &amp;amp; ship&lt;/p&gt;"}]})
    assert (j["id"], j["location"], j["posted"], j["description"]) == ("greenhouse:t:1", "Paris", "2026-11-10", "Build things & ship"), j
    j = one("lever", [{"id": "ab", "text": "Data Engineer", "hostedUrl": "https://l/ab", "createdAt": 1763000000000,
                       "categories": {"location": "Paris"}, "descriptionPlain": "Intro.",
                       "lists": [{"text": "You", "content": "<li>Python</li><li>SQL</li>"}]}])
    assert (j["posted"], j["title"], j["description"]) == ("2025-11-13", "Data Engineer", "Intro. You Python SQL"), j
    j = one("ashby", {"jobs": [{"id": "u1", "title": "AI Engineer", "jobUrl": "https://a/u1", "location": "Paris",
                                "publishedAt": "2026-11-01T08:00:00.000+00:00", "descriptionPlain": "Do  AI.\nNow", "isRemote": True}]})
    assert (j["location"], j["posted"], j["description"]) == ("Paris, Remote", "2026-11-01", "Do AI. Now"), j
    j = one("smartrecruiters", {"content": [{"id": "77", "name": "Data Engineer", "releasedDate": "2026-10-30T00:00:00Z",
                                             "location": {"city": "Paris", "country": "fr"}}]})
    assert (j["location"], j["url"], j["_detail"].endswith("/postings/77"), j["description"]) == (
        "Paris, FR", "https://jobs.smartrecruiters.com/t/77", True, ""), j
    assert smartrecruiters_description({"jobAd": {"sections": {"jobDescription": {"text": "<p>Hi <i>you</i></p>"},
                                                               "qualifications": {"text": "Python"}}}}) == "Hi you Python"
    j = one("workable", {"jobs": [{"shortcode": "ABC", "title": "ML Engineer", "url": "https://w/ABC", "city": "Paris",
                                   "country": "France", "published_on": "2026-11-05", "description": "<p>Text</p>"}]})
    assert (j["location"], j["posted"], j["description"]) == ("Paris, France", "2026-11-05", "Text"), j
    am = {"hits": 1, "jobs": [{"id_icims": "10591962", "title": "Systems Engineer", "job_path": "/en/jobs/10591962/systems-engineer",
          "normalized_location": "Lille, Hauts-de-France, FRA", "posted_date": "October 29, 2026",
          "description": "Build<br/>things", "basic_qualifications": "<ul><li>Python</li></ul>", "preferred_qualifications": "AWS"}]}
    j = one("amazon", am)
    assert (j["id"], j["url"], j["location"], j["posted"], j["description"]) == (
        "amazon:t:10591962", "https://www.amazon.jobs/en/jobs/10591962/systems-engineer", "Lille, Hauts-de-France, FRA",
        "2026-10-29", "Build things Python AWS"), j
    assert detect_url("https://www.amazon.jobs/en/search?base_query=machine+learning+engineer&loc_query=Paris%2C+France") == (
        "amazon", "machine learning engineer", False)
    assert detect_url("https://www.amazon.jobs/en/")[:2] == ("amazon", "")
    assert feed_for("amazon", "ml eng", False, "https://www.amazon.jobs/en/search?base_query=ml+eng&loc_query=Paris%2C+France") == (
        "https://www.amazon.jobs/en/search.json?base_query=ml+eng&result_limit=100&offset=0")
    assert amazon_url("ml", "KOR").endswith("&country=KOR")
    assert detect_url(amazon_url("ml eng", "Paris", 100))[:2] == ("amazon", "ml eng")
    assert token_candidates("Open AI", "https://www.openai.jobs/x") == ["openai", "open-ai"], token_candidates("Open AI", "https://www.openai.jobs/x")
    assert token_candidates("Coupang", "https://www.coupang.jobs/en/jobs/") == ["coupang"]
    assert token_candidates("", "careers.doctolib.com") == ["doctolib"]
    assert token_candidates("Acme Corp", "https://acme.io") == ["acmecorp", "acme-corp", "acme"]
    j = one("recruitee", {"offers": [{"id": 9, "title": "Data Engineer", "careers_url": "https://r/o/9", "location": "Paris, France",
                                      "published_at": "2026-11-02 09:00:00 UTC", "description": "<div>Desc</div>"}]})
    assert (j["id"], j["posted"], j["description"]) == ("recruitee:t:9", "2026-11-02", "Desc"), j

    cfg = {"searches": [{"query": "AI engineer", "location": "Paris, Île-de-France, France"},
                        {"query": "machine learning engineer", "location": "Paris, Île-de-France, France"},
                        {"query": "data engineer", "location": "Paris, Île-de-France, France"},
                        {"query": "Mistral AI alternance", "location": "Paris, Île-de-France, France"}],
           "target_companies": ["Mistral AI"], "exclude_words": ["senior", "lead", "staff"], "exclude_companies": ["BadCo"]}
    groups = keyword_groups(cfg)
    assert groups == [["ai", "engineer"], ["ml", "engineer"], ["data", "engineer"]], groups

    def keep(title, loc="Paris, France", company="Acme"):
        j = {"title": title, "location": loc, "company": company}
        return title_ok(title, groups) and location_ok(loc, cfg) and not excluded(j, cfg)

    assert keep("Ingénieur IA (H/F)")
    assert keep("Machine Learning Engineers", "Paris")
    assert keep("ML Engineer", "Remote - EMEA")
    assert keep("Data Engineer", "")
    assert not keep("Senior Data Engineer")
    assert not keep("Data Engineer", "London, UK")
    assert not keep("Sales Manager")
    assert not keep("Data Engineer", company="BadCo Inc")
    assert not keep("Staff AI Engineer")
    g = keyword_groups({"searches": [{"query": "(AI engineer) OR (machine learning engineer VIE)"}], "target_companies": []})
    assert g == [["ai", "engineer"], ["ml", "engineer"]], g
    assert title_ok("Machine Learning Engineer - Paris", g) and not title_ok("Data Analyst", g)
    print("self-test OK")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("detect", help="print the platform, token and feed URL for a careers URL")
    d.add_argument("url")
    d.add_argument("--name", default="", help="company name, used to guess the board when the page gives nothing")
    f = sub.add_parser("fetch", help="fetch, normalise and filter every company's feed")
    f.add_argument("--companies", required=True)
    f.add_argument("--settings", required=True)
    f.add_argument("--seen")
    f.add_argument("--out")
    f.add_argument("--dry-run", action="store_true", help="do not update companies.json or the seen file")
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "detect":
        print(json.dumps(detect(a.url, name=a.name), ensure_ascii=False))
    elif a.cmd == "fetch":
        run_fetch(a)
    else:
        p.error("need a command (detect, fetch) or --self-test")


if __name__ == "__main__":
    main()
