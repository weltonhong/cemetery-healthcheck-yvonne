# Cemetery Online Health Check

Streamlit web app that runs a 60-90 second online presence audit on a
cemetery prospect at a trade show booth or for cold-outreach prep, and
produces a branded one-page Ring Ring Marketing PDF scorecard.

This is the deployable slice of the
`tradeshow-healthcheck-cemetery` skill from the internal Powerhouse
repo. It contains only the health check code -- no client data, no
other skills.

CTA routes to **Yvonne Reese** (Yvonne.Reese@RingRingMarketing.com).

## Run locally

```bash
cd my-skills/tradeshow-healthcheck-cemetery/webapp
pip install -r requirements.txt

# On Mac/Linux:
export GOOGLE_API_KEY=...
export SCRAPINGBEE_API_KEY=...

# On Windows (PowerShell):
# $env:GOOGLE_API_KEY="..."
# $env:SCRAPINGBEE_API_KEY="..."

streamlit run app.py
```

Open <http://localhost:8501>.

## Deploy to Streamlit Cloud

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to <https://share.streamlit.io> -> **Create app** -> **Deploy from GitHub**.
3. Settings:
   - **Repository:** `weltonhong/cemetery-healthcheck-yvonne`
   - **Branch:** `main`
   - **Main file path:** `my-skills/tradeshow-healthcheck-cemetery/webapp/app.py`
   - **Python version:** 3.12
4. Open **Advanced settings** -> **Secrets** and paste:
   ```toml
   GOOGLE_API_KEY = "AIzaSy..."
   SCRAPINGBEE_API_KEY = "..."
   ```
5. Click **Deploy**. First build takes 2-4 minutes.

Target URL: `cemetery-healthcheck-yvonne.streamlit.app`

## What gets scanned

| Check | Source |
|-------|--------|
| Google Reviews | Google Places API (cemetery-tuned grading) |
| Google 3-Pack (per city + cemetery plots in home city) | Google SERP via UULE |
| Google SEO (per city + cemetery plots in home city) | ScrapingBee + UULE |
| Google Ads (per bucket) | Parsed from same SERP HTML; empty buckets framed as "open lane" |
| Website (8 cemetery-vertical checks) | requests + PageSpeed Insights API |
| Reviews snapshot | Google + Facebook + Yelp |

Each check produces a letter grade. Overall grade is the average of
the graded checks; "Unable to verify" website audits are excluded.

## Search buckets

For every city the rep enters, we run **cemetery [city] [state]**.
For the home city only, we ALSO run **cemetery plots [city] [state]**
because that's the preneed-buyer search and the highest-intent
commercial query in this vertical.

## Cemetery-vertical website checks (8 graded)

1. Real photos (no stock CDN, no generic alt text — candles / doves / crosses)
2. PageSpeed mobile score >= 50
3. Family/owner / management About story or long operating history
4. Preneed contact form / "schedule a property tour" CTA
5. LocalBusiness schema (Cemetery subtype counts)
6. Google reviews widget
7. Property tour photos — gallery / aerial / sections showing actual grounds
8. Inventory / availability info — explicit mention of plots, mausoleum,
   columbarium, cremation gardens, green burial, etc.

Plus two non-graded data points: **property map / section finder** and
detected **platform** (CemSites, Pontem, Buoh, Webcemeteries, plus
generic WordPress / Squarespace / Wix).

## Reviews grading scale

Cemeteries get far fewer reviews than service-business verticals
because plot buyers don't typically leave reviews like service
experiences do. The scale reflects that:

| Grade | Threshold |
|-------|-----------|
| A | 30+ reviews OR more than top competitor |
| B | 15-29 |
| C | 5-14 |
| D | 1-4 |
| F | 0 |

## Repo layout

```
my-skills/
  tradeshow-healthcheck-cemetery/
    SKILL.md
    scripts/
      health_check.py        # Orchestrator - runs all checks in parallel
      google_serp_rank.py    # Real Google SERP via ScrapingBee
      website_audit.py       # Cemetery-vertical homepage scrape + heuristics
      pdf_generator.py       # Branded RRM one-page PDF + Calendly QR
      verify_qr.py           # Decodes generated QR to confirm Calendly URL
    webapp/
      app.py                 # Streamlit UI
      requirements.txt
      assets/
        rrm_logo.jpg
      README.md
  quick-intel/
    scripts/
      google_intel.py        # Google Places lookup (target + competitors)
```

## API keys you need

| Key | What it powers | Where to get it |
|-----|----------------|-----------------|
| `GOOGLE_API_KEY` | Google Places + Geocoding + PageSpeed Insights | Google Cloud Console |
| `SCRAPINGBEE_API_KEY` | Real Google SERP rendering | scrapingbee.com |

Both keys must be set in `os.environ` (locally) or in Streamlit Cloud
**Secrets** (deployed). The webapp mirrors `st.secrets` into `os.environ`
at startup so the underlying scripts pick them up.

## Calendly QR

The Calendly QR code on the bottom of the PDF is regenerated fresh on
every PDF build from `pdf_generator.CALENDLY_URL`. To swap reps later,
change that one constant.

To verify the QR points where you expect:

```bash
python my-skills/tradeshow-healthcheck-cemetery/scripts/verify_qr.py
```
