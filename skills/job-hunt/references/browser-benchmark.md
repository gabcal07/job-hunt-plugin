# Browser benchmark: Lightpanda vs Chrome DevTools (2026-11-21)

Every page was loaded one at a time, from the same IP, with no LinkedIn login in either browser.

## LinkedIn public job pages (5 Paris postings)
| | Pages with the full description | Time per page |
|---|---|---|
| **Lightpanda** | **5/5** (2,000–7,500 chars) | **0.8–1.1 s** |
| Chrome DevTools | 1/5: the other 4 got LinkedIn's sign-in shell (~1,600 chars, no description) | 1.0–1.6 s |

LinkedIn serves the full guest page to Lightpanda, but sends a real Chrome a "sign in to see more" page.

## Careers sites with no job API
| Site | Lightpanda | Notes |
|---|---|---|
| Google | ✅ 6 job links, 2.4 s | |
| Microsoft (`apply.careers.microsoft.com`) | ✅ 4 job links, 6.9 s | The old `jobs.careers.microsoft.com` URL drops the filters in both browsers |
| IBM | ✅ 12 job links, 3.4 s | |
| Upstage (`careers.upstage.ai`) | ✅ 48 job links, 5.8 s | |
| Naver | ⚠️ page loads, but job links are built by script | Read the listing text with `markdown`, not links |
| SAP | ❌ Cloudflare bot check | Chrome was blocked too in the test run |

## Decision
- **Lightpanda is the default** for every page that doesn't need a login: LinkedIn job pages and careers sites. It is faster and gets more of the content.
- **Chrome DevTools is the fallback**, and the first choice for pages that need a login, such as a LinkedIn profile, because it keeps the user's session.
- Pages behind a Cloudflare bot check (SAP) can't be read with either browser. Mark them `blocked`.
