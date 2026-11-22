#!/usr/bin/env python3
"""Optional Apify source (REST API, stdlib only): LinkedIn jobs through Apify's servers, and Welcome to the Jungle.

Opt-in: does nothing without a token. Token from $APIFY_TOKEN, else the file given with --token-file
(the plugin's SessionStart hook writes the token from the plugin settings to ${CLAUDE_PLUGIN_DATA}/apify_token).

  apify.py status [--token-file F]                       -> "no token" | "ok: $1.23 of $5.00 used this month" | "budget reached ..."
  apify.py wttj --settings S.json --seen seen.json --out R/wttj.json [--token-file F] [--dry-run]
  apify.py --self-test
The LinkedIn source is used from linkedin_search.py (--source auto|apify|guest).
Exit 0 always for status/wttj: an unusable Apify is a note, never a failed run.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is needed: install it from python.org (Windows: also `winget install Python.Python.3.12`).")
for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

API = "https://api.apify.com/v2/"
LINKEDIN_ACTOR = "valig~linkedin-jobs-scraper"
WTTJ_ACTOR = "bebity~welcome-to-the-jungle-jobs-scraper"
MONTHLY_STOP = 4.50       # free plan is $5/month; keep a margin for manual runs
RUN_CAP = 0.10            # max charge per actor run
LINKEDIN_FIELDS = "id,url,title,companyName,location,postedDate,description,applicationsCount,experienceLevel,contractType"
FRANCE = ("france", "paris", "lyon", "marseille", "toulouse", "lille", "nantes", "bordeaux", "nice", "rennes", "strasbourg")


class ApifyUnavailable(Exception):
    pass


def token(token_file=None):
    t = os.environ.get("APIFY_TOKEN", "").strip()
    if not t and token_file and os.path.isfile(token_file):
        with open(token_file, encoding="utf-8") as f:
            t = f.read().strip()
    return t or None


class Apify:
    def __init__(self, tok, monthly_stop=MONTHLY_STOP):
        self.tok, self.monthly_stop, self.spent_this_run = tok, monthly_stop, 0.0

    def fetch(self, method, url, body=None, timeout=60):
        """(status, parsed JSON or None). Overridden in the self-test."""
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + self.tok, "Content-Type": "application/json",
                                              "User-Agent": "job-hunt-plugin"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ApifyUnavailable("network error: %s" % e)

    def usage(self):
        """(used_usd, max_usd) for the current monthly cycle."""
        code, d = self.fetch("GET", API + "users/me/limits")
        if code == 401:
            raise ApifyUnavailable("the Apify token was refused (check it in the plugin settings)")
        if code != 200 or not d:
            raise ApifyUnavailable("could not read Apify usage (HTTP %s)" % code)
        d = d.get("data", d)
        return float(d.get("current", {}).get("monthlyUsageUsd", 0)), float(d.get("limits", {}).get("maxMonthlyUsageUsd", 5))

    def check_budget(self):
        used, cap = self.usage()
        stop = min(self.monthly_stop, cap * 0.9)
        if used + self.spent_this_run >= stop:
            raise ApifyUnavailable("monthly budget reached: $%.2f of $%.2f used (stops at $%.2f)" % (used, cap, stop))
        return used, cap

    def run(self, actor, inp, max_items, fields=None, max_charge=RUN_CAP):
        q = {"maxTotalChargeUsd": max_charge, "maxItems": max_items, "timeout": 280, "clean": "true"}
        if fields:
            q["fields"] = fields
        code, d = self.fetch("POST", API + "acts/%s/run-sync-get-dataset-items?%s" % (actor, urllib.parse.urlencode(q)), inp, timeout=310)
        if code in (200, 201):
            self.spent_this_run += max_charge  # upper bound; the real figure comes from usage()
            return d or []
        reason = {401: "the Apify token was refused", 402: "Apify credit used up for this month",
                  403: "the token lacks permission", 408: "the Apify run took too long",
                  429: "Apify is rate-limiting"}.get(code, "Apify HTTP %s" % code)
        raise ApifyUnavailable(reason)


# ---------------------------------------------------------------- LinkedIn via valig/linkedin-jobs-scraper
def title_groups(query):
    """'(AI engineer) OR (data engineer)' -> ['AI engineer', 'data engineer']."""
    return [g.strip() for g in re.findall(r"\(([^()]*)\)", query)] or [query.strip()]


def linkedin_input(s, limit, exclude_words, skip_ids, date_posted):
    groups = title_groups(s["query"])
    inp = {"keywords": " OR ".join(groups), "location": s["location"], "datePosted": date_posted, "limit": limit,
           "titleInclude": groups}
    if exclude_words:
        inp["titleExclude"] = list(exclude_words)
    if skip_ids:
        inp["skipJobId"] = list(skip_ids)
    params = [{"key": k, "value": ",".join(map(str, s[f]))} for k, f in (("f_E", "experience"), ("f_JT", "job_type"),
                                                                         ("f_WT", "workplace")) if s.get(f)]
    if params:
        inp["urlParam"] = params
    return inp


def linkedin_job(it):
    jid = str(it.get("id") or re.sub(r"\D", "", str(it.get("url", "")).rstrip("/").split("-")[-1]))
    url = str(it.get("url") or "https://www.linkedin.com/jobs/view/" + jid).split("?", 1)[0]
    apps = it.get("applicationsCount")
    return {"id": jid, "url": url, "title": it.get("title") or "", "company": it.get("companyName") or "",
            "location": it.get("location") or "", "posted": (it.get("postedDate") or "")[:10],
            "description": " ".join(str(it.get("description") or "").split()),
            "applicants": ("%s applicants" % apps) if apps not in (None, "") else "",
            "seniority": it.get("experienceLevel") or "", "employment_type": it.get("contractType") or "",
            "job_function": "", "industries": "", "source": "linkedin", "via": "apify"}


# ---------------------------------------------------------------- Welcome to the Jungle
def wttj_job(it):
    """Field names as the actor returns them (checked 2026-11-22): publicUrl, published_at, office{city,country},
    organization{name}, description_text + profile_text, contract_type, reference/objectID."""
    org = it.get("organization") or {}
    off = it.get("office") or {}
    loc = ", ".join(x for x in (off.get("city"), off.get("country")) if x) if isinstance(off, dict) else str(off)
    desc = " ".join((str(it.get("description_text") or it.get("description_markdown") or "") + " "
                     + str(it.get("profile_text") or "")).split())
    return {"id": "wttj:" + str(it.get("reference") or it.get("objectID") or it.get("slug")), "url": it.get("publicUrl") or "",
            "title": it.get("name") or "", "company": org.get("name", "") if isinstance(org, dict) else str(org),
            "location": loc, "posted": str(it.get("published_at") or "")[:10], "description": desc,
            "employment_type": str(it.get("contract_type") or ""), "source": "wttj", "via": "apify"}


def french_cities(cfg):
    out = []
    for s in cfg.get("searches", []):
        city = s["location"].split(",")[0].strip()
        if any(w in s["location"].lower() for w in FRANCE) and city not in out:
            out.append(city)
    return out


def run_wttj(a):
    from linkedin_search import job_key  # noqa: E402
    from careers import excluded  # noqa: E402  same exclude-word and exclude-company rule as the careers feeds
    cfg = json.load(open(a.settings, encoding="utf-8"))
    seen = json.load(open(a.seen, encoding="utf-8")) if a.seen and os.path.exists(a.seen) else {}
    res = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "jobs": [], "note": ""}
    cities, tok = french_cities(cfg), token(a.token_file)
    if not tok or not cities:
        res["note"] = "skipped: no Apify token" if not tok else "skipped: no city in France"
    else:
        cli = Apify(tok)
        try:
            cli.check_budget()
            titles = list(dict.fromkeys(g for s in cfg["searches"] for g in title_groups(s["query"])))
            per = cfg.get("apify_per_search", 15)
            got = set()
            for city in cities:
                for title in titles:  # WTTJ's search doesn't understand "A OR B": one query per title
                    inp = {"action": "get-jobs", "query": title, "searchInTitleOnly": True, "countryCode": "FR", "city": city,
                           "postedWithinDays": 7, "includeDetails": True, "maxItems": per}
                    for it in cli.run(WTTJ_ACTOR, inp, per):
                        j = wttj_job(it)
                        if (j["id"] in got or j["id"] in seen or job_key(j["company"], j["title"]) in seen
                                or excluded(j, cfg)):
                            continue
                        got.add(j["id"])
                        res["jobs"].append(j)
        except ApifyUnavailable as e:
            res["note"] = "stopped: %s" % e
    if a.seen and not a.dry_run and res["jobs"]:
        today = date.today().isoformat()
        for j in res["jobs"]:
            seen.setdefault(j["id"], today)
            seen.setdefault(job_key(j["company"], j["title"]), today)
        json.dump(seen, open(a.seen, "w", encoding="utf-8"), indent=1)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"wttj": len(res["jobs"]), "note": res["note"]}))


def status(a):
    tok = token(a.token_file)
    if not tok:
        print("no token")
        return
    try:
        used, cap = Apify(tok).check_budget()
        print("ok: $%.2f of $%.2f used this month" % (used, cap))
    except ApifyUnavailable as e:
        print(str(e))


# ---------------------------------------------------------------- self-test
def self_test():
    class Fake(Apify):
        def __init__(self, replies, **kw):
            super().__init__("t", **kw)
            self.replies, self.calls = list(replies), []

        def fetch(self, method, url, body=None, timeout=60):
            self.calls.append((method, url, body))
            return self.replies.pop(0)
    lim = lambda used: (200, {"data": {"current": {"monthlyUsageUsd": used}, "limits": {"maxMonthlyUsageUsd": 5}}})
    c = Fake([lim(1.2), (201, [{"id": 1}])])
    assert c.check_budget() == (1.2, 5.0) and c.run(LINKEDIN_ACTOR, {}, 15, LINKEDIN_FIELDS) == [{"id": 1}]
    assert "maxTotalChargeUsd=0.1" in c.calls[1][1] and "fields=id%2Curl" in c.calls[1][1] and "Bearer" not in c.calls[1][1]
    for code, word in ((402, "credit"), (401, "refused"), (429, "rate"), (408, "too long")):
        try:
            Fake([(code, None)]).run(LINKEDIN_ACTOR, {}, 5)
            assert False, code
        except ApifyUnavailable as e:
            assert word in str(e), (code, e)
    try:
        Fake([lim(4.6)]).check_budget()
        assert False, "budget"
    except ApifyUnavailable as e:
        assert "budget" in str(e)
    try:
        Fake([(401, None)]).check_budget()
        assert False
    except ApifyUnavailable as e:
        assert "refused" in str(e)
    assert title_groups("(AI engineer) OR (data engineer VIE)") == ["AI engineer", "data engineer VIE"]
    inp = linkedin_input({"query": "(AI engineer) OR (ML engineer)", "location": "Paris, France", "experience": [2], "workplace": [1, 3]},
                         15, ["senior"], ["123"], "r86400")
    assert inp["keywords"] == "AI engineer OR ML engineer" and inp["titleInclude"] == ["AI engineer", "ML engineer"]
    assert inp["urlParam"] == [{"key": "f_E", "value": "2"}, {"key": "f_WT", "value": "1,3"}] and inp["skipJobId"] == ["123"]
    j = linkedin_job({"id": "4450285827", "url": "https://fr.linkedin.com/jobs/view/x-4450285827?trk=1", "title": "AI Expert",
                      "companyName": "Candriam", "location": "Paris", "postedDate": "2026-11-21T10:00:00Z",
                      "description": "Build\n  agents", "applicationsCount": 42, "experienceLevel": "Entry level"})
    assert j["url"].endswith("4450285827") and j["posted"] == "2026-11-21" and j["description"] == "Build agents"
    assert j["applicants"] == "42 applicants" and j["seniority"] == "Entry level" and j["via"] == "apify"
    w = wttj_job({"reference": "GALAD_9K", "publicUrl": "https://www.welcometothejungle.com/fr/companies/x/jobs/y", "name": "AI Engineer",
                  "organization": {"name": "Galadrim"}, "office": {"city": "Paris", "country": "France"},
                  "description_text": "Notre équipe", "profile_text": "Python", "published_at": "2026-11-22T09:00:02Z",
                  "contract_type": "full_time"})
    assert w["id"] == "wttj:GALAD_9K" and w["company"] == "Galadrim" and w["location"] == "Paris, France", w
    assert w["posted"] == "2026-11-22" and w["description"] == "Notre équipe Python" and w["url"].startswith("https://www.wel"), w
    assert french_cities({"searches": [{"location": "Paris, Île-de-France, France"}, {"location": "Seoul, South Korea"},
                                       {"location": "Paris, Île-de-France, France"}]}) == ["Paris"]
    os.environ.pop("APIFY_TOKEN", None)
    assert token(None) is None
    print("self-test OK")


def main():
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--token-file")
    s = sub.add_parser("wttj")
    s.add_argument("--settings", required=True)
    s.add_argument("--seen")
    s.add_argument("--out", required=True)
    s.add_argument("--token-file")
    s.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    status(a) if a.cmd == "status" else run_wttj(a)


if __name__ == "__main__":
    main()
