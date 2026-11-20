#!/usr/bin/env python3
"""Validate state/settings.json (shape defined in references/settings-schema.md).

Usage: settings.py --check PATH | --self-test.  Stdlib only, Python 3.9+.
"""
import argparse
import copy
import json
import sys

LEVELS = "1 intern, 2 entry, 3 associate, 4 mid-senior, 5 director, 6 executive"
JOB_TYPES = "FPCTIVO"
# key -> (required, checker name)
TOP = {
    "searches": True, "target_companies": True, "bonus_companies": True, "exclude_words": True,
    "exclude_companies": True, "top_n": True, "min_score": True, "cv_language": True,
    "max_per_search": True, "max_total": True,
    "contracts": False, "level": False, "remote": False, "start": False, "salary_min": False,
    "preferences": False, "notes": False,
}
SEARCH_KEYS = {"query", "location", "experience", "job_type", "workplace", "posted_within_hours", "why"}


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v):
    return is_int(v) or isinstance(v, float)


def str_list(d, key, errs, where=""):
    v = d[key]
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        errs.append("%s%s must be a list of strings" % (where, key))


def check_search(i, s, errs):
    p = "searches[%d]" % i
    if not isinstance(s, dict):
        errs.append("%s must be an object" % p)
        return
    for k in s:
        if k not in SEARCH_KEYS:
            errs.append("%s.%s: unknown key (allowed: %s)" % (p, k, ", ".join(sorted(SEARCH_KEYS))))
    for k in ("query", "location"):
        if not isinstance(s.get(k), str) or not s[k].strip():
            errs.append("%s.%s must be a non-empty string" % (p, k))
    for k, ok, hint in (
        ("experience", lambda x: is_int(x) and 1 <= x <= 6, "is not a LinkedIn level (use 1 intern ... 6 executive)"),
        ("job_type", lambda x: isinstance(x, str) and len(x) == 1 and x in JOB_TYPES,
         "is not a LinkedIn job type (use one of F,P,C,T,I,V,O)"),
        ("workplace", lambda x: is_int(x) and 1 <= x <= 3, "is not a workplace code (use 1 on-site, 2 remote, 3 hybrid)"),
    ):
        if k not in s:
            continue
        if not isinstance(s[k], list):
            errs.append("%s.%s must be a list" % (p, k))
            continue
        for x in s[k]:
            if not ok(x):
                errs.append("%s.%s: %r %s" % (p, k, x, hint))
    if "posted_within_hours" in s and not (is_int(s["posted_within_hours"]) and s["posted_within_hours"] > 0):
        errs.append("%s.posted_within_hours must be a positive whole number of hours" % p)
    if "why" in s and not isinstance(s["why"], str):
        errs.append("%s.why must be a string" % p)


def validate(d):
    """Return a list of plain-English problems (empty when valid)."""
    if not isinstance(d, dict):
        return ["settings.json must be a JSON object"]
    errs = []
    for k in d:
        if k not in TOP:
            errs.append("%s: unknown top-level key" % k)
    for k, req in TOP.items():
        if req and k not in d:
            errs.append("%s: required key is missing" % k)
    if "searches" in d:
        s = d["searches"]
        if not isinstance(s, list) or not s:
            errs.append("searches must be a non-empty list")
        else:
            for i, x in enumerate(s):
                check_search(i, x, errs)
    for k in ("target_companies", "bonus_companies", "exclude_words", "exclude_companies", "contracts", "notes"):
        if k in d:
            str_list(d, k, errs)
    for k, lo, hi in (("top_n", 1, 100), ("min_score", 0, 100), ("max_per_search", 1, 1000), ("max_total", 1, 1000)):
        if k in d and not (is_int(d[k]) and lo <= d[k] <= hi):
            errs.append("%s: %r is not a whole number from %d to %d" % (k, d[k], lo, hi))
    if "cv_language" in d and d["cv_language"] not in ("match", "en", "fr"):
        errs.append("cv_language: %r is not allowed (use match, en or fr)" % (d["cv_language"],))
    for k in ("level", "remote", "start", "preferences"):
        if k in d and not isinstance(d[k], str):
            errs.append("%s must be a string" % k)
    if "salary_min" in d and d["salary_min"] is not None and not is_num(d["salary_min"]):
        errs.append("salary_min must be a number or null")
    return errs


def summary(d):
    s = d["searches"]
    uniq = lambda xs: list(dict.fromkeys(xs))
    return ("%d searches\n  cities: %s\n  titles: %s\n  target companies: %s\n  top_n: %d" % (
        len(s), "; ".join(uniq(x["location"] for x in s)), "; ".join(uniq(x["query"] for x in s)),
        ", ".join(d["target_companies"]) or "none", d["top_n"]))


SAMPLE = {
    "searches": [{"query": "AI engineer", "location": "Paris, France", "experience": [2], "job_type": ["F"],
                  "workplace": [1, 3], "posted_within_hours": 24, "why": "title x city"}],
    "target_companies": ["Mistral AI"], "bonus_companies": [], "exclude_words": ["senior"],
    "exclude_companies": [], "top_n": 5, "min_score": 65, "cv_language": "match",
    "max_per_search": 15, "max_total": 60, "salary_min": None, "notes": [],
}


def self_test():
    assert validate(SAMPLE) == [], validate(SAMPLE)
    bad = copy.deepcopy(SAMPLE)
    bad["searches"].append({"query": "x", "location": "y"})
    bad["searches"].append({"query": "x", "location": "y", "experience": [7]})
    errs = validate(bad)
    assert errs == ["searches[2].experience: 7 is not a LinkedIn level (use 1 intern ... 6 executive)"], errs
    bad = dict(SAMPLE, foo=1)
    assert validate(bad) == ["foo: unknown top-level key"], validate(bad)
    bad = dict(SAMPLE, searches=[])
    assert validate(bad) == ["searches must be a non-empty list"], validate(bad)
    assert "1 searches" in summary(SAMPLE)
    print("self-test OK")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", metavar="PATH")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if not a.check:
        p.error("need --check PATH or --self-test")
    try:
        with open(a.check, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        print("cannot read %s: %s" % (a.check, e))
        sys.exit(1)
    errs = validate(d)
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    print(summary(d))


if __name__ == "__main__":
    main()
