# Cemetery Health Check - Streamlit Web App

Browser version of the cemetery trade show / cold-outreach health check.
Reuses the existing scripts in `../scripts/` (`health_check.py`,
`google_serp_rank.py`, `website_audit.py`, `pdf_generator.py`) without
rebuilding any logic.

CTA routes to **Yvonne Reese** (Yvonne.Reese@RingRingMarketing.com).

## Local run

```bash
cd my-skills/tradeshow-healthcheck-cemetery/webapp
pip install -r requirements.txt

# On Windows the underlying scripts also try a PowerShell fallback for env
# vars, so existing user env vars work without extra setup. On Mac/Linux,
# export them in your shell first:
export GOOGLE_API_KEY=...
export SCRAPINGBEE_API_KEY=...

streamlit run app.py
```

Open <http://localhost:8501>.

## Streamlit Cloud deploy

1. Push the clean slice repo (`weltonhong/cemetery-healthcheck-yvonne`) to GitHub.
2. On <https://share.streamlit.io>, point a new app at:
   - **Repo:** weltonhong/cemetery-healthcheck-yvonne
   - **Branch:** main
   - **Main file path:** `my-skills/tradeshow-healthcheck-cemetery/webapp/app.py`
3. In **App settings → Secrets**, add:
   ```toml
   GOOGLE_API_KEY = "AIza..."
   SCRAPINGBEE_API_KEY = "..."
   ```
4. Deploy. The webapp pulls secrets into `os.environ` at startup.

## How it works

- `app.py` adds `../scripts/` to `sys.path` and imports `health_check` and
  `pdf_generator` directly.
- `health_check.run_health_check()` runs in a background thread. Its `print()`
  output is streamed to a `st.code()` placeholder so the rep watches the
  scan in real time.
- `pdf_generator.RRM_LOGO_PATH` is monkey-patched to point at
  `webapp/assets/rrm_logo.jpg` so the PDF renders correctly in cloud
  environments where the original Windows D:\ share isn't available.
- `pdf_generator.get_desktop_path` is monkey-patched to a tempdir so the
  PDF is written to a server-writable location, then read back and
  offered via `st.download_button`.
- The Calendly QR code is regenerated fresh on every PDF build from the
  `CALENDLY_URL` constant in `pdf_generator.py`.

## Cemetery-specific behavior

- Search buckets: `cemetery [city]` per city plus `cemetery plots [city]`
  in the home city only (preneed-buyer signal).
- Reviews grading: A=30+ OR > top competitor (cemeteries get fewer
  reviews than service-business verticals).
- Directory filter strips Find A Grave, BillionGraves, Interment.net,
  Legacy.com from organic results.
- Ad block: empty buckets framed as "open lane" opportunity rather
  than failure.
- Website checks: real photos, PageSpeed, family/owner story, preneed
  form / schedule-a-tour, schema, reviews widget, property tour photos,
  inventory/availability info. Property map and platform reported as
  non-graded data points.
