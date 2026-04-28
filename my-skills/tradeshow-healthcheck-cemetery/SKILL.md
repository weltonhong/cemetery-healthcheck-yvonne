---
name: tradeshow-healthcheck-cemetery
description: "Trade show / cold-outreach booth tool for CEMETERY prospects. Runs a fast (60-90 second) online presence audit on a cemetery prospect across 1-3 cities they serve and prints a live scorecard, then generates a branded one-page Ring Ring Marketing PDF. Scans Google reviews, 3-Pack (cemetery + cemetery plots), SEO organic, website, reviews snapshot, and competitor ads in parallel. CTA routes to Yvonne Reese. Use when 'tradeshow healthcheck cemetery', 'health check cemetery', 'cemetery booth audit', 'cemetery trade show audit', 'health check [cemetery] [city] [state]'."
allowed-tools: Bash, Read, Write, AskUserQuestion
---

# TRADESHOW HEALTH CHECK - CEMETERY

## What This Skill Does

Runs a fast online presence audit on a cemetery prospect at a trade show booth or for cold outreach prep. The whole scan takes 60-90 seconds and produces:

1. A live scorecard printed to the terminal as each check completes (so the prospect sees it happening in real time at a booth)
2. A branded one-page Ring Ring Marketing PDF saved to the Desktop

This is a fork of `tradeshow-healthcheck-funeralhome`, retooled for cemetery vocabulary, search intent (cemetery + cemetery plots), and website checks (property tour photos, preneed contact form, inventory/availability info, property map). The CTA still routes to Yvonne Reese.

## Cemetery vs funeral home framing

Cemeteries operate on a **preneed-dominant** revenue model. Most plots, mausoleum crypts, columbarium niches, and markers are sold BEFORE death, not at-need. The vocabulary throughout this skill reflects that:

- "preneed inquiries" / "preneed sales" = the dominant frame
- "interment inquiries" = at-need families who need burial when no plot was preplanned
- "preneed appointments" / "property tours" = the conversion mechanism
- "lot sales" / "interment volume" = how cemetery volume is measured

Cemeteries also draw from a **larger service radius** than funeral homes. Far fewer cemeteries per market, and families will drive past closer ones to bury near existing family graves or at a specific religious / cultural cemetery. 2-3 cities is the realistic norm.

## Input

**ALWAYS prompt the user for input before running. Never auto-fill, never assume, never use positional args from the slash command line.**

The rep is at a trade show booth typing the prospect's live answers. You must ask each question and wait for the answer.

### Required workflow

Ask each question on its own line, **one at a time**, blank, with **no pre-filled answers, no parenthetical suggestions, and no inferences**. Wait for the user's reply before asking the next question.

Order:

1. `Cemetery name:`
2. `Home city:`
3. `State (2-letter):`
4. `Second city (or skip):`
5. `Third city (or skip):`

**Hard rules:**
- Never infer the home city from the cemetery name. "Mountain View Cemetery" does NOT mean any specific city. Ask anyway.
- Never write parenthetical guesses after a question.
- Never batch multiple questions in one prompt. One question, wait, next question.
- After each user answer, the next message is just the next blank question label - no acknowledgment text, no restating what they said.

If the user answers "skip", "none", "n/a", or leaves a city blank, skip that city. Encourage filling all 3 — cemeteries draw from a wide radius.

### Why prompt every time

The prospect's service area changes with every booth conversation. Auto-filling or guessing breaks the booth flow.

## How To Run

```bash
python my-skills/tradeshow-healthcheck-cemetery/scripts/health_check.py "<cemetery>" "<city1>" "<state>" ["<city2>"] ["<city3>"]
```

Example:
```bash
python my-skills/tradeshow-healthcheck-cemetery/scripts/health_check.py "Forest Lawn Memorial Park" "Glendale" "CA"
```

The script:
1. Pulls Google Places data for the prospect + top cemetery competitors (from City1)
2. Fans out parallel checks: 3-Pack (per city, plus cemetery plots in home city), SEO (per city, plus cemetery plots), Website, Reviews
3. Builds the Ads check from each bucket's SERP HTML (no separate fetch)
4. Prints a live scorecard to stdout as each check completes
5. Saves raw data to `temp_health_check.json` next to the script
6. Generates a branded Ring Ring Marketing PDF on the OneDrive Desktop

## Search Queries

| Bucket | Query | Where it runs |
|---|---|---|
| Cemetery (primary) | `cemetery [city] [state]` | Every city |
| Cemetery plots (preneed) | `cemetery plots [city] [state]` | Home city only |

`cemetery plots` is the preneed-shopper query and the highest commercial intent search in this vertical. We run it in the home city only so the report shows ranking for both the general cemetery search and the preneed-buyer search without paying for a third query in every secondary city.

## What It Scans

| Check | Source | Output |
|-------|--------|--------|
| Google Reviews | google_intel.py (Google Places API) | Target reviews + top competitor reviews + gap. Cemetery-tuned grading scale (cemeteries get fewer reviews than service-business verticals). |
| Google 3-Pack | Per-bucket Google SERP -> Local Map Pack | In/out of top 3 from each bucket. Small-market handling: 3-pack often only has 1-2 results. |
| SEO Organic | ScrapingBee + UULE per bucket (Playwright fallback) | Rank for "cemetery [city] [state]" from each city; "cemetery plots [city] [state]" from home city. Heavy directory filtering (Find A Grave dominates cemetery SERPs). |
| Website | requests.get + PageSpeed Insights API + subpage fetches | 8 hard checks: real photos, PageSpeed mobile, family/owner story, preneed contact form, LocalBusiness/Cemetery schema, Google reviews widget, property tour photos, inventory/availability info, plus property map (counted as part of inventory check). Detects platform (CemSites, Pontem, Buoh, Webcemeteries, plus generic WordPress/Squarespace/Wix). |
| Reviews Snapshot | Google Places + DDG search | Google + Facebook + Yelp counts/links |
| Competitor Ads | Same SERP HTML from SEO check; parses `div#tads` | Real Google ad advertisers per bucket. Domain-only matching filters out corporate operator ads (StoneMor, SCI/Dignity, Carriage). |

## Grading Scale

**Reviews are graded on a cemetery-specific scale.** Cemeteries get far fewer reviews than service-business verticals because plot buyers don't typically leave reviews like service experiences do.

| Area | A | B | C | D | F |
|------|---|---|---|---|---|
| Reviews | 30+ OR more than top competitor | 15-29 | 5-14 | 1-4 | 0 |
| 3-Pack | Found in all bucket combos | Found in most | Found in 1 | - | Not found anywhere |
| SEO | Top 10 in all buckets | Top 10 in most | Top 10 in 1 | - | Not in top 10 anywhere |
| Ads | Prospect running in all buckets | Running in most | Running in 1 | - | Not running in any |
| Website | 8/8 checks pass (or N/A if blocked) | 6-7 | 3-5 | 1-2 | 0 |
| Overall | Average of all grades except those marked "Unable to verify" |

**No competitor available:** In small markets the prospect may have no real cemetery competitor. The scorecard prints "Limited competition in [city]" and the reviews grade is computed against the absolute scale only.

**No advertisers detected:** Many cemeteries don't run ads in smaller markets. The scorecard frames this as opportunity rather than failure: "No cemetery in [city] is running Google Ads — open lane."

## Unable to Verify (Website)

When the prospect's website returns HTTP 403, times out, or fails SSL, the website check returns `unverified: true` instead of grading F. The terminal shows "Unable to verify -- Website blocked our scan" and the PDF shows grade "N/A". This grade is excluded from the overall grade calculation.

## On-Screen Output Format

```
============================================
ONLINE HEALTH CHECK | Forest Lawn Memorial Park Glendale, CA
============================================

GOOGLE REVIEWS:
  847 reviews, 4.6 stars

TOP COMPETITOR:
  Mountain View Cemetery -- 312 reviews, 4.5 stars

GOOGLE LOCAL MAP RANKINGS:
  cemetery / Glendale:        FOUND rank 1 (Top 3: ...)
  cemetery plots / Glendale:  NOT FOUND (Top 3: ...)
  Grade: C

GOOGLE ORGANIC RANKINGS (SEO):
  cemetery / Glendale CA:        Rank 2
  cemetery plots / Glendale CA:  Not in top 10
  Grade: C

GOOGLE ADS:
  cemetery / Glendale: No ads detected (open lane)
  cemetery plots / Glendale: Pierce Brothers, Eternal Hills
  Forest Lawn Memorial Park: Not running
  Grade: F

WEBSITE:
  Real photos:              Yes
  PageSpeed mobile:         62/100 (PASS)
  Family/owner story:       Yes
  Preneed contact form:     Yes
  LocalBusiness schema:     Yes
  Google reviews widget:    No
  Property tour photos:     Yes
  Inventory / availability: Yes (plots, mausoleum, columbarium)
  Platform:                 WordPress
  Grade: B

REVIEWS SNAPSHOT:
  Google:   847 reviews, 4.6 stars
  Facebook: Page found
  Yelp:     ? reviews

============================================
OVERALL GRADE: C    (scan time: 38s)
============================================
```

## PDF Output

Saved to OneDrive Desktop as:
```
HealthCheck_<CemeteryName>_<YYYY-MM-DD>.pdf
```

Contents:
- RRM brand header
- Cemetery name + scan date
- Big overall grade banner
- 5-row scorecard with grades and per-bucket details
- 2 specific recommendations targeting the worst grades
- Footer CTA bar with Yvonne Reese contact + Calendly QR (regenerated fresh from CALENDLY_URL on every build)

## CTA / Footer

Footer copy:
> Every week these gaps stay open, families looking for cemetery plots and preneed arrangements are finding your competitors instead. We close these gaps for cemeteries across the country. Call today.

Contact:
- Yvonne Reese, Sales Consultant
- Yvonne.Reese@RingRingMarketing.com
- Ring Ring Marketing | (888) 383-2848
- QR -> https://calendly.com/yvonne-reese-ringringmarketing/yvonne-reese-marketing-audit

## Files

```
my-skills/tradeshow-healthcheck-cemetery/
  SKILL.md
  scripts/
    health_check.py      # Main orchestrator (run this)
    google_serp_rank.py  # Real-Google SERP rank checker (ScrapingBee + Playwright fallback)
    website_audit.py     # Cemetery-specific homepage scrape + heuristics
    pdf_generator.py     # Reportlab branded RRM PDF, regenerates QR from CALENDLY_URL at build time
    verify_qr.py         # Decodes the generated QR with pyzbar to confirm Calendly URL
  webapp/
    app.py
    requirements.txt
    assets/
```

## Dependencies

- `reportlab` (PDF) - install with `pip install reportlab`
- `qrcode[pil]` (Calendly QR) - install with `pip install "qrcode[pil]"`
- `requests` (HTTP)
- `playwright` (SERP fallback) - install with `pip install playwright && playwright install chrome`
- `GOOGLE_API_KEY` env var (Places + Geocoding)
- `SCRAPINGBEE_API_KEY` env var (preferred SERP backend)
- Reuses `my-skills/quick-intel/scripts/google_intel.py` (with `--vertical "cemetery"`)

## SERP Backend Selection

Same two-tier backend as the funeral home version:

1. **ScrapingBee with `custom_google=true` + UULE** - Primary path. ~25 credits per query. With 2 cities + cemetery plots in the home city, that's ~75 credits per scan.
2. **Playwright with stealth + UULE + persisted cookies** - Fallback if `SCRAPINGBEE_API_KEY` is not set OR ScrapingBee returns an error.

Never falls back to DuckDuckGo.

## Boundaries

| Always | Ask First | Never |
|--------|-----------|-------|
| Run all checks in parallel | Before changing the grading scale | Block on a single slow check past 30 seconds |
| Print results live as they arrive | Before adding a new search bucket | Fabricate review counts or ranks |
| Save the PDF to OneDrive Desktop | Before changing recommendation copy | Conflate corporate operator ads (StoneMor / SCI / Carriage) with the local cemetery running ads |
| Use only data returned by tool calls in this session | | Skip the live terminal output (the prospect needs to see it) |

## Why This Exists

At a cemetery industry convention, Yvonne walks up to a prospect's booth, asks for the cemetery name and 1-2 nearby towns families travel from, types one command, and 60 seconds later hands the manager a printed scorecard with their grades, their gaps across their service area, and a call to action. Same skill also works as cold-outreach prep when Yvonne is dialing cemetery prospects from her CRM.
