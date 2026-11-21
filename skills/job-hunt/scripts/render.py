"""Render the CV or a cover letter to PDF (stdlib HTML -> headless Chrome). No installs needed.

Run with the system Python 3.9 (only Google Chrome is required):
  python3 scripts/render.py cv --profile P.json --lang fr --out cv.pdf [--photo photo.jpg]
  python3 scripts/render.py letter --profile P.json --letter L.json --lang fr --out letter.pdf

Inputs are JSON. A .yaml/.yml input is accepted only if PyYAML is importable (else exit 2).
Writes <out>.html next to the PDF. Env CHROME overrides the Chrome binary.
Exit 2 = input not JSON, 3 (and "PAGES=<n>" on stderr) = CV longer than one page, 4 = no Chrome.
"""
import argparse, json, os, re, shutil, subprocess, sys
from html import escape as e
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


def main():
    if sys.argv[1:] == ["--check-chrome"]:
        print("Chrome OK:", find_chrome())
        return
    a = argparse.ArgumentParser()
    a.add_argument("kind", choices=["cv", "letter"])
    a.add_argument("--profile", required=True)
    a.add_argument("--letter")
    a.add_argument("--lang", default="en", choices=list(LABELS))
    a.add_argument("--out", required=True)
    a.add_argument("--photo", default="")
    args = a.parse_args()

    p = load(args.profile)
    for k in ("headline", "summary"):
        v = p.get(k)
        if isinstance(v, dict):
            p[k] = v.get(args.lang) or v.get("en") or ""
    L = LABELS[args.lang]
    if args.kind == "cv":
        photo_uri = Path(args.photo).resolve().as_uri() if args.photo and Path(args.photo).is_file() else ""
        doc = cv_html(p, args.lang, L, photo_uri)
    else:
        if not args.letter:
            sys.exit("--letter is required for 'letter'")
        doc = letter_html(p, load(args.letter), args.lang, L)

    chrome = find_chrome()
    out = Path(args.out).resolve()
    html = out.with_suffix(".html")
    html.write_text(doc, encoding="utf-8")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", html.as_uri()], check=True, capture_output=True)
    pages = len(re.findall(rb"/Type\s*/Page\b(?!s)", out.read_bytes()))
    print(f"{out} pages={pages}")
    if args.kind == "cv" and pages > 1:
        print(f"WARNING PAGES={pages}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
