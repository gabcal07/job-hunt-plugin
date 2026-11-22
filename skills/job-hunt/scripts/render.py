"""Render the CV or a cover letter to PDF (stdlib HTML -> headless Chrome). No installs needed.

Python 3.10+, standard library only (plus Google Chrome for PDFs):
  python3 scripts/render.py cv --profile P.json --lang fr --out cv.pdf [--design elegant|ats|classic] [--docx] [--photo photo.jpg]
      [--accent "#6B1E2E"] [--heading-font serif|sans]
  python3 scripts/render.py letter --profile P.json --letter L.json --lang fr --out letter.pdf
  python3 scripts/render.py check --pdf cv.pdf [--docx cv.docx] --profile P.json --lang fr [--keywords a,b | --keywords-file notes.md] [--json]
  python3 scripts/render.py --self-test
--design elegant (default) is single column with an accent colour, optional round photo, a 4-column skills grid and
**bold** results; ats is the plain single-column layout (no photo); classic is the two-column sidebar design.
The DOCX always uses the plain ats layout. **bold** markers are stripped everywhere except elegant.

Inputs are JSON. A .yaml/.yml input is accepted only if PyYAML is importable (else exit 2).
Writes <out>.html next to the PDF. Env CHROME overrides the Chrome binary.
Exit 2 = input not JSON, 3 (and "PAGES=<n>" on stderr) = CV longer than one page, 4 = no Chrome,
5 = unparseable date (stderr "DATE? <value>"), 6 = `check` failed.
"""
import argparse, json, os, re, shutil, subprocess, sys, unicodedata, zipfile, zlib
from html import escape as e
from html.parser import HTMLParser
from pathlib import Path
if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is needed: install it from python.org (Windows: also `winget install Python.Python.3.12`).")
for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    _s.reconfigure(encoding="utf-8", errors="replace")

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LABELS = {
    "en": dict(work="Work experience", education="Education", projects="Projects", skills="Skills",
               languages="Languages", hobbies="Hobbies", certifications="Certifications", subject="Subject"),
    "fr": dict(work="Expérience professionnelle", education="Formation", projects="Projets", skills="Compétences",
               languages="Langues", hobbies="Centres d'intérêt", certifications="Certifications", subject="Objet"),
}
ICONS = {
    'email': '<path d="M2 6.5 12 13l10-6.5V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v.5zM22 9 12 15.5 2 9v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9z"/>',
    'linkedin': '<path d="M3 3h18v18H3V3zm3.2 6.8v8.5h2.6V9.8H6.2zM7.5 5.6a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm3.1 4.2v8.5h2.6v-4.5c0-1.2.5-1.9 1.4-1.9s1.3.7 1.3 1.9v4.5h2.6v-5c0-2.2-1.2-3.7-3-3.7-1 0-1.9.5-2.3 1.2V9.8h-2.6z" fill-rule="evenodd"/>',
    'github': '<path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.4 1.1 2.9.8.1-.7.4-1.1.6-1.4-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.300.1-2.700 0 0 .8-.3 2.800 1a9.600 9.600 0 0 1 5.100 0c2-1.300 2.800-1 2.800-1 .5 1.400.2 2.400.1 2.700.6.700 1 1.600 1 2.700 0 3.900-2.400 4.700-4.600 5 .4.300.7.900.7 1.800v2.700c0 .3.2.6.7.5A10 10 0 0 0 12 2z"/>',
    'phone': '<path d="M6.6 10.8a15 15 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25c1.100.37 2.300.57 3.600.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.500a1 1 0 0 1 1 1c0 1.300.2 2.500.57 3.600a1 1 0 0 1-.25 1l-2.200 2.200z"/>',
    'location': '<path d="M12 2a7 7 0 0 0-7 7c0 5.200 7 13 7 13s7-7.800 7-13a7 7 0 0 0-7-7zm0 9.500A2.500 2.500 0 1 1 12 6.500a2.500 2.500 0 0 1 0 5z"/>',
}


def find_chrome():
    cands = [os.environ.get("CHROME"),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    cands += [shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    if os.environ.get("ProgramFiles"):
        cands.append(os.path.join(os.environ["ProgramFiles"], "Google", "Chrome", "Application", "chrome.exe"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    print("Google Chrome is needed to make PDFs: install it from google.com/chrome", file=sys.stderr)
    sys.exit(4)


def load(path):
    text = Path(path).read_text(encoding="utf-8")
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            print(f"{path}: convert to JSON (PyYAML is not installed)", file=sys.stderr)
            sys.exit(2)
        return yaml.safe_load(text)
    return json.loads(text)


def page(lang, title, css, body):
    return (f'<!DOCTYPE html>\n<html lang="{e(lang)}">\n<head>\n<meta charset="utf-8">\n<title>{e(title)}</title>\n'
            f'<style>\n{css}</style>\n</head>\n<body>\n{body}</body>\n</html>\n')


def ul(items, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f"<ul{c}>" + "".join(f"<li>{e(str(i))}</li>" for i in items or []) + "</ul>"


def contact_li(key, c):
    v = c.get(key)
    if not v:
        return ""
    if key == "email":
        inner = f'<a href="mailto:{e(v)}">{e(v)}</a>'
    elif key == "linkedin":
        inner = f'<a href="https://{e(v.replace("https://", ""))}">{e(v)}</a>'
    elif key == "github":
        inner = f'<a href="{e(v)}">{e(v)}</a>'
    else:
        inner = f"<span>{e(v)}</span>"
    return f'<li><svg viewBox="0 0 24 24">{ICONS[key]}</svg>{inner}</li>\n'


def entry(x, org_keys, title_html=None, date_key="dates"):
    org = ", ".join(x[k] for k in org_keys if x.get(k))
    org_div = f'<div class="org">{e(org)}</div>\n' if org_keys else ""
    t = title_html or e(x.get("title", ""))
    return (f'<section class="entry">\n<div class="row"><span class="title">{t}</span>'
            f'<span class="date">{e(x.get(date_key, ""))}</span></div>\n{org_div}{ul(x.get("bullets"))}\n</section>\n')


def section(title, items, builder):
    return f"<h2>{e(title)}</h2>\n" + "".join(builder(x) for x in items) if items else ""


def cv_html(p, lang, L, photo_uri):
    c = p.get("contact") or {}
    s = '<aside class="side">\n'
    if photo_uri:
        s += f'<img class="photo" src="{e(photo_uri)}" alt="">\n'
    s += f'<div class="name">{e(p.get("name", ""))}</div>\n<ul class="contact">\n'
    s += "".join(contact_li(k, c) for k in ("email", "linkedin", "github", "phone", "location")) + "</ul>\n"
    s += f'<h2 class="rule">{e(L["skills"])}</h2>\n'
    if p.get("languages"):
        s += f'<h2 style="margin-top:2mm">{e(L["languages"])}</h2>\n<ul>'
        s += "".join(f'<li class="lang"><b>{e(x.get("name", ""))}</b> <span class="lvl">{e(x.get("level", ""))}</span></li>'
                     for x in p["languages"]) + "</ul>\n"
    for group, items in (p.get("skills") or {}).items():
        s += f"<h2>{e(group)}</h2>\n{ul(items)}\n"
    if p.get("certifications"):
        s += f'<h2>{e(L["certifications"])}</h2>\n{ul(p["certifications"])}\n'
    if p.get("hobbies"):
        s += f'<h2 class="rule">{e(L["hobbies"])}</h2>\n{ul(p["hobbies"], "cols")}\n'
    s += '</aside>\n\n<main class="main">\n'
    if p.get("summary"):
        s += f'<p class="summary">{e(p["summary"])}</p>\n'
    s += section(L["work"], p.get("experience"), lambda x: entry(x, ("company", "location")))
    s += section(L["education"], p.get("education"), lambda x: entry(x, ("school", "location")))

    def proj(x):
        t = e(x.get("title", ""))
        if x.get("url"):
            t = f'<a href="{e(x["url"])}">{t}</a>'
        return entry(x, (), t, "date")
    s += section(L["projects"], p.get("projects"), proj)
    s += "</main>\n"
    return page(lang, f'{p.get("name", "")} - CV', (ASSETS / "cv.css").read_text(encoding="utf-8"), s)


def letter_html(p, letter, lang, L):
    c = p.get("contact") or {}
    contact = "".join(f"<span>{e(c[k])}</span>" for k in ("email", "phone", "location", "linkedin", "github") if c.get(k))
    city = c["location"].split(",")[0] + ", " if c.get("location") else ""
    s = (f'<header class="band">\n<div class="name">{e(p.get("name", ""))}</div>\n<div class="contact">{contact}</div>\n</header>\n'
         f'<div class="body">\n<div class="date">{e(city + letter.get("date", ""))}</div>\n')
    if letter.get("company"):
        s += f'<div class="recipient">{e(letter["company"])}</div>\n'
    s += f'<div class="subject">{e(L["subject"])} : {e(letter.get("subject", ""))}</div>\n'
    s += f'<p class="greeting">{e(letter.get("greeting", ""))}</p>\n'
    s += "".join(f'<p class="para">{e(x)}</p>\n' for x in letter.get("paragraphs") or [])
    s += f'<p class="para">{e(letter.get("closing", ""))}</p>\n<p class="sign">{e(p.get("name", ""))}</p>\n</div>\n'
    return page(lang, f'{p.get("name", "")} - {letter.get("subject", "")}',
                (ASSETS / "letter.css").read_text(encoding="utf-8"), s)


# ---------------------------------------------------------------- text normalisation
_PLAIN = {**{c: "'" for c in "‘’‚′"}, **{c: '"' for c in "“”„″"},
          **{c: "-" for c in "–—‒―−"}, "…": "...",
          **{c: " " for c in "   "}, "•": "-",
          **{c: None for c in "​‌‍⁠﻿­"}}
_PLAIN_TR = str.maketrans(_PLAIN)
# letters are read by people, not ATS parsers: keep French NBSP before ; : ! ? and typographic quotes, drop only invisibles
_LETTER_TR = str.maketrans({c: None for c in "\u200b\u200c\u200d\u2060\ufeff\u00ad"})


def plain(s):
    """ASCII-fold typographic punctuation only; letters (accents, Korean) and << >> are kept."""
    return s.translate(_PLAIN_TR) if isinstance(s, str) else s


def letter_plain(s):
    return s.translate(_LETTER_TR) if isinstance(s, str) else s


def deep(o, f):
    if isinstance(o, str):
        return f(o)
    if isinstance(o, list):
        return [deep(x, f) for x in o]
    if isinstance(o, dict):
        return {f(k) if isinstance(k, str) else k: deep(v, f) for k, v in o.items()}
    return o


def fold(s):
    """Accent- and case-insensitive form with collapsed whitespace, for matching."""
    s = unicodedata.normalize("NFKD", plain(s))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)).casefold()).strip()


# ---------------------------------------------------------------- dates
MONTHS = {"en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
          "fr": "janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.".split()}
_MIDX = {n: i for i, names in enumerate([
    "jan janv january janvier", "feb fev fevr fevrier february", "mar mars march", "apr avr april avril",
    "may mai", "jun juin june", "jul juil july juillet", "aug aout august", "sep sept september septembre",
    "oct october octobre", "nov november novembre", "dec december decembre"]) for n in names.split()}
_PRESENT = {"present", "current", "now", "ongoing"}


def _date_part(tok):
    t = fold(tok).replace(".", "")
    if t in _PRESENT:
        return ("now", None)
    m = re.fullmatch(r"([^\W\d_]+)(?: (\d{4}))?", t)
    if m and m[1] in _MIDX:
        return (_MIDX[m[1]], m[2])
    if re.fullmatch(r"\d{4}", t):
        return (None, t)
    raise ValueError(tok)


def fmt_dates(s, lang):
    """Normalise to 'Mon YYYY - Mon YYYY' (or one date). Unparseable: 'DATE? <value>' on stderr, exit 5."""
    s = plain(s).strip()
    if not s:
        return ""
    try:
        parts = [_date_part(x) for x in re.split(r"\s*-\s*", s)]
        if len(parts) > 2:
            raise ValueError(s)
        if len(parts) == 2 and isinstance(parts[0][0], int) and parts[0][1] is None:
            if parts[1][1] is None:
                raise ValueError(s)
            parts[0] = (parts[0][0], parts[1][1])  # "Mar - June 2023"
        out = []
        for m, y in parts:
            if m == "now":
                out.append("Present" if lang == "en" else "Présent")
            elif m is None:
                out.append(y)
            elif y is None:
                raise ValueError(s)
            else:
                out.append(f"{MONTHS[lang][m]} {y}")
        return " - ".join(out)
    except ValueError:
        print(f"DATE? {s}", file=sys.stderr)
        sys.exit(5)


def prep(p, lang, dates=True):
    """Resolve {en,fr} fields, ASCII-fold every string, normalise every date field."""
    p = dict(p)
    for k in ("headline", "summary"):
        if isinstance(p.get(k), dict):
            p[k] = p[k].get(lang) or p[k].get("en") or ""
    p = deep(p, plain)
    if dates:
        for sec, key in (("experience", "dates"), ("education", "dates"), ("projects", "date")):
            for x in p.get(sec) or []:
                if x.get(key):
                    x[key] = fmt_dates(x[key], lang)
    return p


# ---------------------------------------------------------------- ATS content model (shared by HTML and DOCX)
ATS_H = {
    "en": dict(summary="Summary", work="Experience", education="Education", projects="Projects", skills="Skills",
               languages="Languages", certifications="Certifications"),
    "fr": dict(summary="Profil", work="Expérience professionnelle", education="Formation", projects="Projets",
               skills="Compétences", languages="Langues", certifications="Certifications"),
}
CONTACT_L = {
    "en": dict(email="Email", phone="Phone", location="Location", linkedin="LinkedIn", github="GitHub"),
    "fr": dict(email="E-mail", phone="Téléphone", location="Localisation", linkedin="LinkedIn", github="GitHub"),
}


def ats_blocks(p, lang):
    """Linear list of ('name'|'h2'|'p'|'ul', payload); a 'p' payload is [(text, style)] with style ''|'b'|'t'|'d'."""
    H, CL, c = ATS_H[lang], CONTACT_L[lang], p.get("contact") or {}
    B = [("name", p.get("name", ""))]
    if p.get("headline"):
        B.append(("p", [(p["headline"], "b")]))
    for keys in (("email", "phone", "location"), ("linkedin", "github")):
        items = [f"{CL[k]}: {c[k]}" for k in keys if c.get(k)]
        if items:
            B.append(("p", [(" | ".join(items), "")]))
    if p.get("summary"):
        B += [("h2", H["summary"]), ("p", [(p["summary"], "")])]

    def entries(key, org_keys, date_key, heading):
        if not p.get(key):
            return
        B.append(("h2", heading))
        for x in p[key]:
            org = ", ".join(x[k] for k in org_keys if x.get(k))
            runs = [(x.get("title", ""), "t")]
            if org:
                runs.append((" - " + org, ""))
            if key == "projects" and x.get("url"):
                runs.append((" - " + x["url"], ""))
            if x.get(date_key):
                runs += [(" | ", ""), (x[date_key], "d")]
            B.append(("p", runs))
            if x.get("bullets"):
                B.append(("ul", [str(i) for i in x["bullets"]]))
    entries("experience", ("company", "location"), "dates", H["work"])
    entries("education", ("school", "location"), "dates", H["education"])
    entries("projects", (), "date", H["projects"])
    if p.get("skills"):
        B.append(("h2", H["skills"]))
        B += [("p", [(g + ":", "b"), (" " + ", ".join(items), "")]) for g, items in p["skills"].items()]
    if p.get("languages"):
        B += [("h2", H["languages"]), ("p", [(", ".join(
            f'{x.get("name", "")} ({x["level"]})' if x.get("level") else x.get("name", "") for x in p["languages"]), "")])]
    if p.get("certifications"):
        B += [("h2", H["certifications"]), ("ul", [str(i) for i in p["certifications"]])]
    return B


def ats_text(blocks):
    return "\n".join("".join(t for t, _ in v) if k == "p" else "\n".join(v) if k == "ul" else v for k, v in blocks)


def ats_html(p, lang):
    s = ""
    for k, v in ats_blocks(p, lang):
        if k == "name":
            s += f"<h1>{e(v)}</h1>\n"
        elif k == "h2":
            s += f"<h2>{e(v)}</h2>\n"
        elif k == "p":
            s += "<p>" + "".join(f'<span class="{st}">{e(t)}</span>' if st else e(t) for t, st in v) + "</p>\n"
        else:
            s += ul(v) + "\n"
    return page(lang, f'{p.get("name", "")} - CV', (ASSETS / "ats.css").read_text(encoding="utf-8"), s)


# ---------------------------------------------------------------- elegant: single column, accent colour, optional photo
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def unbold(s):
    """Drop **bold** markers (ats/classic/docx); elegant renders them as <b>."""
    return _BOLD.sub(r"\1", s) if isinstance(s, str) else s


def rich(s):
    return _BOLD.sub(r"<b>\1</b>", e(str(s)))


def tint(hex_, k=.75):
    """Mix a #rrggbb colour with white, for the thin rules."""
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(v + (255 - v) * k):02x}" for v in (r, g, b))


def elegant_html(p, lang, photo_uri="", accent="#1F3A5F", serif=True):
    H, c = ATS_H[lang], p.get("contact") or {}
    link = lambda url, label: f'<a href="{e(url if url.startswith("http") else "https://" + url)}">{e(label)}</a>'
    s = '<div class="head"><div>\n' + f'<h1>{e(p.get("name", ""))}</h1>\n'
    if p.get("headline"):
        s += f'<div class="headline">{e(p["headline"])}</div>\n'
    s += '<div class="contact">' + " · ".join(e(c[k]) for k in ("email", "phone", "location") if c.get(k))
    links = [link(c[k], lbl) for k, lbl in (("linkedin", "Profil LinkedIn" if lang == "fr" else "LinkedIn profile"),
                                            ("github", "GitHub")) if c.get(k)]
    s += ("<br>" + " · ".join(links) if links else "") + "</div>\n</div>\n"
    if photo_uri:
        s += f'<img class="photo" src="{e(photo_uri)}" alt="">\n'
    s += "</div>\n"
    if p.get("summary"):
        s += f'<h2>{e(H["summary"])}</h2>\n<p>{rich(p["summary"])}</p>\n'

    def entries(key, org_keys, date_key):
        out = ""
        for x in p.get(key) or []:
            t = e(x.get("title", ""))
            if x.get("url"):
                t = link(x["url"], x.get("title", ""))
            org = ", ".join(x[k] for k in org_keys if x.get(k))
            out += (f'<div class="entry"><div class="row"><span>{t}</span><span class="d">{e(x.get(date_key, ""))}</span></div>\n'
                    + (f'<div class="org">{e(org)}</div>\n' if org else "")
                    + ("<ul>" + "".join(f"<li>{rich(b)}</li>" for b in x["bullets"]) + "</ul>" if x.get("bullets") else "")
                    + "</div>\n")
        return out
    for key, org_keys, date_key, h in (("experience", ("company", "location"), "dates", "work"),
                                       ("education", ("school", "location"), "dates", "education"),
                                       ("projects", (), "date", "projects")):
        if p.get(key):
            s += f'<h2>{e(H[h])}</h2>\n' + entries(key, org_keys, date_key)
    if p.get("skills"):
        s += f'<h2>{e(H["skills"])}</h2>\n<div class="cols">' + "".join(
            f"<div><b>{e(g)}</b>{ul(items)}</div>" for g, items in p["skills"].items()) + "</div>\n"
    if p.get("languages"):
        s += f'<h2>{e(H["languages"])}</h2>\n<p>' + " · ".join(
            e(f'{x.get("name", "")} ({x["level"]})' if x.get("level") else x.get("name", "")) for x in p["languages"]) + "</p>\n"
    if p.get("certifications"):
        s += f'<h2>{e(H["certifications"])}</h2>\n{ul(p["certifications"])}\n'
    if p.get("hobbies"):
        s += f'<h2>{e(LABELS[lang]["hobbies"])}</h2>\n<p>' + " · ".join(e(h) for h in p["hobbies"]) + "</p>\n"
    hfont = "Georgia, 'DejaVu Serif', serif" if serif else "Calibri, Carlito, 'Helvetica Neue', Arial, sans-serif"
    css = f":root {{ --accent: {accent}; --accent-light: {tint(accent)}; --hfont: {hfont}; }}\n"
    return page(lang, f'{p.get("name", "")} - CV', css + (ASSETS / "elegant.css").read_text(encoding="utf-8"), s)


# ---------------------------------------------------------------- DOCX (WordprocessingML via zipfile)
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _x(s):
    return e(_BAD_XML.sub("", s), quote=False)


def _run(text, style):
    rpr = {"b": "<w:b/>", "t": '<w:b/><w:color w:val="0A1F8F"/>', "d": '<w:color w:val="0A1F8F"/>'}.get(style, "")
    return f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{_x(text)}</w:t></w:r>'


def build_docx(p, lang, path):
    body = ""
    for k, v in ats_blocks(p, lang):
        if k == "name":
            body += f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>{_run(v, "")}</w:p>'
        elif k == "h2":
            body += f'<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>{_run(v, "")}</w:p>'
        elif k == "p":
            body += "<w:p>" + "".join(_run(t, st) for t, st in v) + "</w:p>"
        else:
            body += "".join('<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/>'
                            f"</w:numPr></w:pPr>{_run(i, '')}</w:p>" for i in v)
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="850" w:right="850" w:bottom="850" w:left="850" '
            'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')
    hdr = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    font = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
    parts = {
        "[Content_Types].xml": hdr + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>',
        "_rels/.rels": hdr + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>',
        "word/_rels/document.xml.rels": hdr + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>',
        "word/document.xml": hdr + f'<w:document xmlns:w="{_W}"><w:body>{body}{sect}</w:body></w:document>',
        "word/styles.xml": hdr + f'<w:styles xmlns:w="{_W}"><w:docDefaults><w:rPrDefault><w:rPr>{font}'
            f'<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="{"fr-FR" if lang == "fr" else "en-GB"}"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="30" w:line="252" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:after="30"/></w:pPr><w:rPr><w:b/><w:color w:val="0A1F8F"/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="0A1F8F"/></w:pBdr>'
            '<w:spacing w:before="140" w:after="50"/><w:outlineLvl w:val="1"/></w:pPr>'
            '<w:rPr><w:b/><w:color w:val="0A1F8F"/><w:sz w:val="25"/><w:szCs w:val="25"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:after="10"/></w:pPr></w:style></w:styles>',
        "word/numbering.xml": hdr + f'<w:numbering xmlns:w="{_W}"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>'
            '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
            f'<w:pPr><w:ind w:left="283" w:hanging="283"/></w:pPr><w:rPr>{font}</w:rPr></w:lvl></w:abstractNum>'
            '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>',
        "docProps/core.xml": hdr + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{_x(p.get("name", "") + " - CV")}</dc:title></cp:coreProperties>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in parts.items():  # [Content_Types].xml first, as Word expects
            z.writestr(n, d)


def docx_text(path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return "\n".join("".join(t.text or "" for t in para.iter(f"{{{_W}}}t")) for para in root.iter(f"{{{_W}}}p"))


# ---------------------------------------------------------------- PDF: metadata scrub + text extraction
def scrub_pdf_info(path):
    """Blank /Creator /Producer /Author /Subject string contents in place (same byte length: xref stays valid)."""
    data = bytearray(Path(path).read_bytes())
    for m in list(re.finditer(rb"/(?:Creator|Producer|Author|Subject)\s*(?=[(<])(?!<<)", bytes(data))):
        i = m.end()
        if data[i] == 0x3C:  # hex string
            j = data.index(b">", i)
            data[i + 1:j] = (b"20" * ((j - i - 1) // 2)).ljust(j - i - 1, b"0")
            continue
        depth, j = 1, i + 1
        while j < len(data) and depth:
            c = data[j]
            if c == 0x5C:
                j += 1  # skip the escaped byte (\( \) \\)
            elif c == 0x28:
                depth += 1
            elif c == 0x29:
                depth -= 1
            j += 1
        data[i + 1:j - 1] = b" " * (j - 2 - i)
    Path(path).write_bytes(bytes(data))


def _pdf_objects(data):
    objs, pos, rx = {}, 0, re.compile(rb"(?<!\d)(\d+)\s+\d+\s+obj\b")
    while (m := rx.search(data, pos)):
        s = m.end()
        si, eo = data.find(b"stream", s), data.find(b"endobj", s)
        if eo == -1:
            break
        raw = None
        if si != -1 and si < eo:
            ds = si + 6 + (2 if data[si + 6:si + 8] == b"\r\n" else 1)
            es = data.find(b"endstream", ds)
            dic, raw = data[s:si], data[ds:es]
            if b"/FlateDecode" in dic:
                try:
                    raw = zlib.decompressobj().decompress(raw)
                except zlib.error:
                    raw = b""
            eo = data.find(b"endobj", es)
        else:
            dic = data[s:eo]
        objs[int(m[1])] = (dic, raw)
        pos = eo + 6
    return objs


def _uni(h):
    return bytes.fromhex(h.decode()).decode("utf-16-be", "replace")


def _cmap(data):
    m = re.search(rb"begincodespacerange\s*<([0-9A-Fa-f]+)>", data)
    mp = {}
    for blk in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", blk):
            mp[int(a, 16)] = _uni(b)
    for blk in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for r in re.finditer(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", blk):
            lo, hi, d = int(r[1], 16), int(r[2], 16), r[3]
            if d[:1] == b"[":
                for k, it in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", d)):
                    mp[lo + k] = _uni(it)
            else:
                base, w = int(d[1:-1], 16), len(d) - 2
                for k in range(hi - lo + 1):
                    mp[lo + k] = _uni(format(base + k, f"0{w}x").encode())
    return (len(m[1]) // 2 if m else 2), mp


def _tokens(b):
    i, n = 0, len(b)
    esc = {ord(c): ord(r) for c, r in zip("nrtbf", "\n\r\t\b\f")}
    while i < n:
        c = b[i]
        if c in b" \t\r\n\x00\x0c":
            i += 1
        elif c == 0x25:  # comment
            while i < n and b[i] not in b"\r\n":
                i += 1
        elif c == 0x28:
            depth, i, buf = 1, i + 1, bytearray()
            while i < n and depth:
                ch = b[i]
                if ch == 0x5C:
                    i += 1
                    ch = b[i]
                    if ch in esc:
                        buf.append(esc[ch])
                    elif 48 <= ch <= 55:
                        k = i
                        while k < i + 2 and k + 1 < n and 48 <= b[k + 1] <= 55:
                            k += 1
                        buf.append(int(b[i:k + 1], 8) & 255)
                        i = k
                    elif ch == 13 and b[i + 1:i + 2] == b"\n":
                        i += 1
                    elif ch not in (10, 13):
                        buf.append(ch)
                elif ch == 0x28:
                    depth += 1
                    buf.append(ch)
                elif ch == 0x29:
                    depth -= 1
                    if depth:
                        buf.append(ch)
                else:
                    buf.append(ch)
                i += 1
            yield ("s", bytes(buf))
        elif c == 0x3C and b[i + 1:i + 2] != b"<":
            j = b.index(b">", i)
            h = re.sub(rb"\s", b"", b[i + 1:j]).decode()
            yield ("s", bytes.fromhex(h + "0" * (len(h) % 2)))
            i = j + 1
        elif c in b"[]":
            yield (chr(c), None)
            i += 1
        elif b[i:i + 2] in (b"<<", b">>"):
            i += 2
        else:
            j = i + 1
            while j < n and b[j] not in b" \t\r\n\x00\x0c/[]()<>%":
                j += 1
            w = b[i:j]
            i = j if j > i else i + 1
            if w[:1] == b"/":
                yield ("n", w[1:].decode("latin-1"))
            else:
                try:
                    yield ("f", float(w))
                except ValueError:
                    yield ("o", w.decode("latin-1"))


def pdf_text(path):
    """Minimal stdlib text extractor for Chrome/Skia PDFs: Flate streams, Tj/TJ, ToUnicode CMaps."""
    objs = _pdf_objects(Path(path).read_bytes())
    ref = lambda d, key: (lambda m: int(m[1]) if m else None)(re.search(rb"/" + key + rb"\s+(\d+)\s+0\s+R", d))
    cmaps = {}
    for n, (d, _) in objs.items():
        t = ref(d, b"ToUnicode")
        if t and t in objs and objs[t][1] is not None and re.search(rb"/Type\s*/Font\b", d):
            cmaps[n] = _cmap(objs[t][1])
    out = []
    for n, (d, _) in objs.items():
        if not re.search(rb"/Type\s*/Page\b", d):
            continue
        res = d
        if (r := ref(d, b"Resources")) in objs:
            res = objs[r][0]
        fd = None
        if (m := re.search(rb"/Font\s*<<(.*?)>>", res, re.S)):
            fd = m[1]
        elif (r := ref(res, b"Font")) in objs:
            fd = objs[r][0]
        fonts = {m[1].decode("latin-1"): cmaps.get(int(m[2])) for m in re.finditer(rb"/([^\s/<>\[\]()]+)\s+(\d+)\s+0\s+R", fd or b"")}
        cm = re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+0\s+R)", d)
        refs = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", cm[1])] if cm else []
        content = b"\n".join(objs[r][1] or b"" for r in refs if r in objs)
        out.append(_content_text(content, fonts))
    return "\n".join(out)


def _content_text(content, fonts):
    res, st, stack, font, last_y = [], [], None, None, None

    def dec(b):
        cm = fonts.get(font)
        if not cm:
            return b.decode("latin-1")
        w, mp = cm
        return "".join(mp.get(int.from_bytes(b[i:i + w], "big"), "") for i in range(0, len(b), w))
    for k, v in _tokens(content):
        if k == "[":
            stack = []
        elif k == "]":
            st.append(("a", stack))
            stack = None
        elif stack is not None:
            stack.append((k, v))
        elif k != "o":
            st.append((k, v))
        else:
            ops = [x for x in st]
            st = []
            if v == "Tf" and len(ops) >= 2:
                font = ops[-2][1]
            elif v == "Tj" and ops:
                res.append(dec(ops[-1][1]))
            elif v in ("'", '"') and ops:
                res.append("\n" + dec(ops[-1][1]))
            elif v == "TJ" and ops:
                for ek, ev in ops[-1][1]:
                    if ek == "s":
                        res.append(dec(ev))
                    elif ek == "f" and ev < -250:
                        res.append(" ")
            elif v in ("Td", "TD") and len(ops) >= 2:
                if abs(ops[-1][1]) > 0.5:  # dy != 0: new line; a pure x move is just the next run (spaces are glyphs)
                    res.append("\n")
            elif v == "Tm" and len(ops) >= 6:
                y = ops[-1][1]
                res.append("\n" if last_y is None or abs(y - last_y) > 0.5 else " ")
                last_y = y
            elif v == "T*":
                res.append("\n")
    return "".join(res)


def _html_text(path):
    class T(HTMLParser):
        def __init__(s):
            super().__init__()
            s.out, s.skip = [], 0

        def handle_starttag(s, t, a):
            if t in ("style", "script", "title"):
                s.skip += 1
            else:
                s.out.append("\n")

        def handle_endtag(s, t):
            if t in ("style", "script", "title"):
                s.skip -= 1
            else:
                s.out.append("\n")

        def handle_data(s, d):
            if not s.skip:
                s.out.append(d)
    t = T()
    t.feed(Path(path).read_text(encoding="utf-8"))
    return "".join(t.out)


# ---------------------------------------------------------------- check
def read_keywords(path):
    """'- keyword' lines under a '## Keywords' heading in notes.md (exact posting phrases used in the CV).
    Gaps in the requirements table are deliberately not claimed, so that table is never read."""
    lines, out, on = Path(path).read_text(encoding="utf-8").splitlines(), [], False
    for l in lines:
        if l.startswith("#"):
            on = bool(re.match(r"#+\s*(keywords|mots-cl)", l, re.I))
        elif on and (m := re.match(r"\s*[-*]\s+(.+)", l)):
            out.append(m[1].strip().strip("`"))
    return out


def _terms(kw):
    """A requirement phrase counts as found if the phrase or any of its comma/slash/colon-separated parts is."""
    return [kw] + [t.strip() for t in re.split(r"[,;/:()]| ou | or | et | and ", kw) if len(t.strip()) >= 3 and t.strip() != kw]


def _has(text, term):
    t = fold(term)
    return bool(t) and re.search(r"(?<!\w)" + re.escape(t), text) is not None


def run_checks(text, p, lang, keywords=()):
    ft, lines = fold(text), [fold(l) for l in text.splitlines() if l.strip()]
    head, digits = fold(text[:400]), re.sub(r"\D", "", text[:400])
    c = p.get("contact") or {}
    R = {"name": fold(p.get("name", "")) in head, "email": fold(c.get("email", "")) in head,
         "phone": bool(re.sub(r"\D", "", c.get("phone", ""))) and re.sub(r"\D", "", c["phone"]) in digits}
    pos, miss = 0, []
    for h in [v for k, v in ats_blocks(p, lang) if k == "h2"]:
        hit = next((i for i in range(pos, len(lines)) if lines[i] == fold(h)), None)
        if hit is None:
            miss.append(h)
        else:
            pos = hit + 1
    R["headings_missing"] = miss
    dates = [x.get(k) for sec, k in (("experience", "dates"), ("education", "dates"), ("projects", "date"))
             for x in p.get(sec) or [] if x.get(k)]
    R["dates_missing"] = [d for d in dates if fold(d) not in ft]
    R["titles_missing"] = [x["title"] for x in p.get("experience") or [] if fold(x.get("title", "")) not in ft]
    kws = [k for k in keywords if k.strip()]
    found = {k: next((t for t in _terms(k) if _has(ft, t)), None) for k in kws}
    R["keywords_missing"] = [k for k, v in found.items() if v is None]
    R["keyword_pct"] = round(100 * (len(kws) - len(R["keywords_missing"])) / len(kws), 1) if kws else None
    R["pass"] = (R["name"] and R["email"] and R["phone"] and not miss and not R["dates_missing"]
                 and not R["titles_missing"] and (R["keyword_pct"] is None or R["keyword_pct"] >= 70))
    return R


def extract_pdf(pdf, expected, use_pdftotext=True):
    """Return (text, source). Falls back to the sibling .html when under 50% of the expected text comes out."""
    src, text = "builtin", ""
    try:
        if use_pdftotext and shutil.which("pdftotext"):
            src = "pdftotext"
            text = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, text=True,
                                  encoding="utf-8", check=True).stdout
        else:
            text = pdf_text(pdf)
    except Exception as ex:
        print(f"PDF text extraction failed ({src}): {ex}", file=sys.stderr)
    n = lambda s: len(re.sub(r"\s", "", fold(s)))
    if n(text) < 0.5 * n(expected):
        html = Path(pdf).with_suffix(".html")
        if html.is_file():
            return _html_text(html), "html-fallback"
    return text, src


def do_check(args):
    p = deep(prep(load(args.profile), args.lang), unbold)
    kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else read_keywords(args.keywords_file) if args.keywords_file else []
    expected = ats_text(ats_blocks(p, args.lang))
    sources = {}
    text, src = extract_pdf(args.pdf, expected, not args.no_pdftotext)
    sources[f"pdf ({src})"] = run_checks(text, p, args.lang, kws)
    if args.docx:
        sources["docx"] = run_checks(docx_text(args.docx), p, args.lang, kws)
    ok = all(r["pass"] for r in sources.values())
    if args.json:
        print(json.dumps({"pass": ok, "sources": sources}, ensure_ascii=False, indent=2))
    else:
        for name, r in sources.items():
            yn = lambda b: "ok" if b else "MISSING"
            print(f"source: {name}")
            print(f"  name/email/phone in first 400 chars: {yn(r['name'])} / {yn(r['email'])} / {yn(r['phone'])}")
            print(f"  headings in order: {'ok' if not r['headings_missing'] else 'MISSING ' + ', '.join(r['headings_missing'])}")
            print(f"  dates: {'ok' if not r['dates_missing'] else 'MISSING ' + ', '.join(r['dates_missing'])}")
            print(f"  experience titles: {'ok' if not r['titles_missing'] else 'MISSING ' + '; '.join(r['titles_missing'])}")
            if r["keyword_pct"] is not None:
                print(f"  keyword coverage: {r['keyword_pct']}% (min 70%)"
                      + (f"; missing: {'; '.join(r['keywords_missing'])}" if r["keywords_missing"] else ""))
            print(f"  result: {'PASS' if r['pass'] else 'FAIL'}")
        print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 6)


# ---------------------------------------------------------------- self-test
def self_test():
    assert letter_plain("Objet\u00a0: \u00abIA\u00bb\u200b") == "Objet\u00a0: \u00abIA\u00bb" and plain("a\u00a0b") == "a b"
    import tempfile
    ok = lambda c, m: c or sys.exit(f"SELF-TEST FAIL: {m}")
    ok(plain("‘a’ “b” –—− x… a b c d • z​w «é» 안") ==
       "'a' \"b\" --- x... a b c d - zw «é» 안", "plain")
    cases = {
        ("Sept 2024 - Jan 2025", "en"): "Sep 2024 - Jan 2025", ("Sep 2025 - June 2026", "en"): "Sep 2025 - Jun 2026",
        ("Mar - June 2023", "en"): "Mar 2023 - Jun 2023", ("Aug 2026 - Feb 2027", "en"): "Aug 2026 - Feb 2027",
        ("Sept 2021 - Dec 2026", "en"): "Sep 2021 - Dec 2026", ("July 2024", "en"): "Jul 2024", ("Nov 2026", "en"): "Nov 2026",
        ("Aug 2026 - present", "en"): "Aug 2026 - Present", ("Aug 2026 - présent", "en"): "Aug 2026 - Present",
        ("Sept 2024 - Jan 2025", "fr"): "sept. 2024 - janv. 2025", ("Sep 2025 - June 2026", "fr"): "sept. 2025 - juin 2026",
        ("Mar - June 2023", "fr"): "mars 2023 - juin 2023", ("Aug 2026 - Feb 2027", "fr"): "août 2026 - févr. 2027",
        ("July 2024", "fr"): "juil. 2024", ("Aug 2026 - present", "fr"): "août 2026 - Présent",
        ("Sept. 2026 - présent", "fr"): "sept. 2026 - Présent", ("juil. 2024", "fr"): "juil. 2024",
        ("janv. 2025", "en"): "Jan 2025", ("Août 2026 – Fév. 2027", "en"): "Aug 2026 - Feb 2027",
        ("Déc. 2026", "fr"): "déc. 2026"}
    for (s, l), want in cases.items():
        ok(fmt_dates(s, l) == want, f"fmt_dates({s!r},{l}) = {fmt_dates(s, l)!r}, want {want!r}")
    try:
        fmt_dates("someday", "en")
        ok(False, "bad date should exit 5")
    except SystemExit as x:
        ok(x.code == 5, "bad date exit code")
    schema = ASSETS.parent / "references" / "profile-schema.json"
    for lang in ("en", "fr"):
        p = prep(json.loads(schema.read_text(encoding="utf-8")), lang)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.docx"
            build_docx(p, lang, f)
            ok(zipfile.ZipFile(f).testzip() is None, "docx zip")
            t = docx_text(f)
            R = run_checks(t, p, lang, ["python", "sql", "kubernetes"])
            ok(not R["headings_missing"] and not R["dates_missing"] and not R["titles_missing"], f"docx order {lang}: {R}")
            ok(R["name"] and R["email"] and R["phone"] and R["keyword_pct"] == 66.7 and not R["pass"], f"docx check {lang}: {R}")
            hs = [l for l in t.splitlines() if l in ATS_H[lang].values()]
            ok(hs == [v for k, v in ats_blocks(p, lang) if k == "h2"], f"docx heading order {lang}: {hs}")
    p = prep(json.loads(schema.read_text(encoding="utf-8")), "en")
    txt = ats_text(ats_blocks(p, "en"))
    ok(run_checks(txt, p, "en", ["Python", "déjà vu ou sql"])["pass"], "check on synthetic text")
    bad = txt.replace("Education", "ZZ").replace("Feb 2025", "ZZ")
    R = run_checks(bad, p, "en")
    ok(not R["pass"] and R["headings_missing"] == ["Education"] and R["dates_missing"], "check must flag missing heading/date")
    ok(not run_checks("\n" * 500 + txt, p, "en")["pass"], "name must be within the first 400 chars")
    ok(unbold("Grew **+40%** reach") == "Grew +40% reach" and rich("a **<b>** c") == "a <b>&lt;b&gt;</b> c", "bold markers")
    ok(tint("#000000", .5) == "#808080", "tint")
    for lang in ("en", "fr"):
        p = prep(json.loads(schema.read_text(encoding="utf-8")), lang)
        p["experience"][0]["bullets"] = ["Built a pipeline loading **2M rows** a day"]
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.html"
            f.write_text(elegant_html(p, lang, accent="#6B1E2E"), encoding="utf-8")
            t = _html_text(f)
            ok("**" not in t and "<b>2M rows</b>" in f.read_text(encoding="utf-8"), f"elegant bold {lang}")
            R = run_checks(t, deep(p, unbold), lang, ["python"])
            ok(R["pass"], f"elegant check {lang}: {R}")
    # PDF: metadata scrub (escaped paren) + extractor on a synthetic Chrome-like file
    cm = (b"/CIDInit /ProcSet findresource begin begincmap 1 begincodespacerange <0000> <FFFF> endcodespacerange "
          b"2 beginbfchar <0001> <0048> <0002> <00E9> endbfchar 1 beginbfrange <0003> <0005> <0069> endbfrange endcmap")
    content = zlib.compress(b"BT /F4 12 Tf 1 0 0 1 10 700 Tm [<0001> -20 <0002>] TJ ET\nBT 1 0 0 1 10 680 Tm <000300040005> Tj ET")
    pdf = (b"%PDF-1.4\n1 0 obj\n<</Creator (Mozilla \\(Mac\\) Headless) /Producer (Skia/PDF m1) /Title (Keep)>>\nendobj\n"
           b"2 0 obj\n<</Type /Page /Contents 3 0 R /Resources <</Font <</F4 4 0 R>>>>>>\nendobj\n"
           b"3 0 obj\n<</Filter /FlateDecode /Length " + str(len(content)).encode() + b">>\nstream\n" + content + b"\nendstream\nendobj\n"
           b"4 0 obj\n<</Type /Font /Subtype /Type0 /ToUnicode 5 0 R>>\nendobj\n"
           b"5 0 obj\n<</Length 0>>\nstream\n" + cm + b"\nendstream\nendobj\ntrailer\n<</Info 1 0 R>>\n")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "t.pdf"
        f.write_bytes(pdf)
        scrub_pdf_info(f)
        out = f.read_bytes()
        ok(len(out) == len(pdf) and out.startswith(b"%PDF") and b"Headless" not in out and b"Skia" not in out
           and b"/Title (Keep)" in out and re.search(rb"/Creator \( {24}\)", out), f"scrub: {out[:120]!r}")
        ok(pdf_text(f).split() == ["Hé", "ijk"] or pdf_text(f).split() == ["H", "é", "ijk"], f"pdf_text: {pdf_text(f)!r}")
    print("self-test OK")


def main():
    if sys.argv[1:] == ["--check-chrome"]:
        print("Chrome OK:", find_chrome())
        return
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    a = argparse.ArgumentParser()
    a.add_argument("kind", choices=["cv", "letter", "check"])
    a.add_argument("--profile")
    a.add_argument("--letter")
    a.add_argument("--lang", default="en", choices=list(LABELS))
    a.add_argument("--out")
    a.add_argument("--photo", default="")
    a.add_argument("--design", default="elegant", choices=["elegant", "ats", "classic"])
    a.add_argument("--accent", default="#1F3A5F", help="elegant: accent colour for name, headings, rules")
    a.add_argument("--heading-font", default="serif", choices=["serif", "sans"], help="elegant: heading font")
    a.add_argument("--docx", nargs="?", const=True, default=False,
                   help="cv: flag, also write <out>.docx; check: path of the .docx to check")
    a.add_argument("--pdf")
    a.add_argument("--keywords")
    a.add_argument("--keywords-file")
    a.add_argument("--json", action="store_true")
    a.add_argument("--no-pdftotext", action="store_true", help="check: force the built-in PDF text extractor")
    args = a.parse_args()
    if not args.profile or (args.kind != "check" and not args.out) or (args.kind == "check" and not args.pdf):
        a.error("--profile and --out are required (check: --profile and --pdf)")
    if args.kind == "check":
        return do_check(args)

    p = load(args.profile)
    if args.kind == "cv":
        p = prep(p, args.lang)
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", args.accent):
            a.error("--accent must look like #1F3A5F")
        photo_uri = Path(args.photo).resolve().as_uri() if args.photo and Path(args.photo).is_file() else ""
        if args.photo and not photo_uri:
            print(f"note: photo not found: {args.photo}", file=sys.stderr)
        if args.design == "elegant":
            doc = elegant_html(p, args.lang, photo_uri, args.accent, args.heading_font == "serif")
        elif args.design == "ats":
            if args.photo:
                print("note: the ats design has no photo; --photo ignored", file=sys.stderr)
            doc = ats_html(deep(p, unbold), args.lang)
        else:
            doc = cv_html(deep(p, unbold), args.lang, LABELS[args.lang], photo_uri)
    else:
        if not args.letter:
            sys.exit("--letter is required for 'letter'")
        doc = letter_html(prep(p, args.lang, dates=False), deep(load(args.letter), letter_plain), args.lang, LABELS[args.lang])

    chrome = find_chrome()
    out = Path(args.out).resolve()
    html = out.with_suffix(".html")
    html.write_text(doc, encoding="utf-8")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", html.as_uri()], check=True, capture_output=True)
    scrub_pdf_info(out)
    if args.kind == "cv" and args.docx:
        build_docx(deep(p, unbold), args.lang, out.with_suffix(".docx"))
        print(f"{out.with_suffix('.docx')}")
    pages = len(re.findall(rb"/Type\s*/Page\b(?!s)", out.read_bytes()))
    print(f"{out} pages={pages}")
    if args.kind == "cv" and pages > 1:
        print(f"WARNING PAGES={pages}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
