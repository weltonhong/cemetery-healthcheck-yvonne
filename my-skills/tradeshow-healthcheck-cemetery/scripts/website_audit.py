"""
Website Audit - Trade Show Health Check (Cemetery Edition, Hard Mode)

Fetches a homepage and runs 8 hard checks designed to surface real issues
the cemetery prospect doesn't know about. These are intentionally strict
so most cemetery sites do not score an A.

Cemeteries are a buying-on-sight business: families want to SEE the
property online before driving out to walk the grounds. So real photos,
property tour photos, and clear inventory information are the highest-
leverage gaps. We dropped the funeral-home-specific obituary and
livestream checks (cemeteries don't post obits or stream services) and
added cemetery-specific checks for property visuals, inventory, and a
property map / section finder.

Checks:
  1. Real photos (no stock photo CDNs / generic alt text). Cemeteries are
     stock-heavy in marketing materials -- candles, white doves, cross
     silhouettes -- so we lean hard on this signal.
  2. PageSpeed mobile score >= 50 (Google PageSpeed Insights API)
  3. Family/owner About page that names actual people (or a clear
     ownership / management story).
  4. Preneed contact form / "schedule a tour" CTA -- the #1 cemetery
     conversion mechanism.
  5. LocalBusiness schema markup (Cemetery subtype counts).
  6. Google reviews widget embedded on the site.
  7. Property tour photos -- gallery / drone footage / aerial / sections
     showing the actual grounds, mausoleum, columbarium. Generic stock =
     fail.
  8. Inventory / availability info -- does the site explain what they
     offer (plots, mausoleum crypts, columbarium niches, cremation
     gardens, green burial)? Vague offerings = fail.

Also runs a non-graded "property map" check (does the site have a
property map or section finder so families can locate existing graves?)
and detects platform when possible (CemSites, Pontem, Buoh,
Webcemeteries, plus generic WordPress/Squarespace/Wix). Both surface in
the PDF as data points.

Grade: A (8/8), B (6-7), C (3-5), D (1-2), F (0)

Usage:
    python website_audit.py --url https://example.com
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ----------------------------- helpers -----------------------------


def get_google_api_key():
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "[System.Environment]::GetEnvironmentVariable('GOOGLE_API_KEY', 'User')"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def fetch_page(url, timeout=15):
    if not url:
        return None, None, "no url"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.text, r.status_code, r.url
    except Exception as e:
        return None, None, str(e)


def base_origin(url):
    """Return scheme://host of a URL."""
    try:
        p = urllib.parse.urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return ""


def find_internal_link(html, base_url, url_keywords):
    """Find first <a href> whose path contains any of the keywords."""
    if not html or not base_url:
        return None
    pattern = re.compile(r'<a[^>]+href="([^"]+)"', re.IGNORECASE)
    for m in pattern.finditer(html):
        href = m.group(1).strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        href_low = href.lower()
        for kw in url_keywords:
            if kw in href_low:
                if href.startswith("http"):
                    return href
                if href.startswith("//"):
                    return "https:" + href
                if href.startswith("/"):
                    return base_url + href
                return urllib.parse.urljoin(base_url + "/", href)
    return None


def find_internal_link_by_path(html, base_url, paths):
    """Try a fixed list of candidate paths against the base URL even if no
    matching href appeared on the homepage. Returns the first that fetches
    a 2xx response, else None."""
    if not base_url:
        return None
    for p in paths:
        url = base_url.rstrip("/") + p
        try:
            r = requests.head(url, headers=HEADERS, timeout=8, allow_redirects=True)
            if r.status_code and 200 <= r.status_code < 300:
                return r.url
        except Exception:
            continue
    return None


# ----------------------------- 1. Real photos vs stock -----------------------------

STOCK_INDICATORS = [
    # Stock provider CDNs and URLs
    "shutterstock", "istockphoto", "gettyimages", "stock.adobe",
    "depositphotos", "dreamstime", "123rf.com", "alamy.com", "bigstock",
    "fotolia", "unsplash.com", "pexels.com", "pixabay.com",
    "stocksnap.io", "freepik.com", "canva.com/photos",
    # Common stock filename patterns
    "stock-photo", "stock_photo", "/stock/", "shutterstock_",
    "istock_", "gettyimages-",
]

# Cemetery-vertical generic alt patterns. Heavy emphasis on candles,
# doves, crosses, headstones-in-rows since cemetery sites lean stock.
GENERIC_ALT_PATTERNS = [
    r'alt="[^"]*candle',
    r'alt="[^"]*white\s+dove',
    r'alt="[^"]*sympathy\s+flowers?',
    r'alt="[^"]*cross\s+(silhouette|sunset)',
    r'alt="[^"]*sunset\s+(silhouette|cross)',
    r'alt="[^"]*tombstone',
    r'alt="[^"]*headstone',
    r'alt="[^"]*grieving',
    r'alt="[^"]*sad\s+(woman|man|person)',
    r'alt="[^"]*holding\s+hands',
    r'alt="[^"]*clasped\s+hands',
    r'alt="[^"]*funeral\s+wreath',
    r'alt="[^"]*flowers?\s+on\s+grave',
    r'alt="[^"]*coffin',
]


def check_real_photos(html):
    """Return True if NO stock photo indicators found."""
    html_lower = html.lower()
    for hint in STOCK_INDICATORS:
        if hint in html_lower:
            return False
    generic_alt_hits = 0
    for pat in GENERIC_ALT_PATTERNS:
        if re.search(pat, html_lower):
            generic_alt_hits += 1
            if generic_alt_hits >= 2:
                return False
    return True


# ----------------------------- 2. PageSpeed Insights -----------------------------


def check_pagespeed(url, api_key, timeout=90):
    """Returns dict with score (0-100) and pass (>=50). Retries once."""
    if not api_key:
        sys.stderr.write("[pagespeed] no GOOGLE_API_KEY available\n")
        return {"score": None, "pass": None, "error": "no api key"}
    if not url:
        return {"score": None, "pass": None, "error": "no url"}

    psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "strategy": "mobile",
        "category": "performance",
        "key": api_key,
    }

    last_error = None
    for attempt in (1, 2):
        try:
            r = requests.get(psi_url, params=params, timeout=timeout)
            if r.status_code != 200:
                last_error = f"HTTP {r.status_code}: {r.text[:160]}"
                sys.stderr.write(
                    f"[pagespeed] attempt {attempt} failed for {url}: {last_error}\n"
                )
                continue
            data = r.json()
            score = (
                data.get("lighthouseResult", {})
                .get("categories", {})
                .get("performance", {})
                .get("score")
            )
            if score is None:
                last_error = "no score in response"
                sys.stderr.write(
                    f"[pagespeed] attempt {attempt} returned no score for {url}\n"
                )
                continue
            score_pct = round(score * 100)
            return {"score": score_pct, "pass": score_pct >= 50}
        except Exception as e:
            last_error = str(e)[:200]
            sys.stderr.write(
                f"[pagespeed] attempt {attempt} exception for {url}: {last_error}\n"
            )

    return {"score": None, "pass": None, "error": last_error}


# ----------------------------- 3. Family/owner About story -----------------------------

ABOUT_URL_KEYWORDS = [
    "/about", "/our-story", "/our-history", "/who-we-are", "/family",
    "/our-family", "/ownership", "/management",
]
ABOUT_PATH_FALLBACKS = [
    "/about", "/about-us", "/our-story", "/who-we-are", "/our-history",
    "/our-family",
]
# Signals that real ownership / management is named on the page.
FAMILY_OWNER_SIGNALS = [
    r"\bowner\b",
    r"\bowners\b",
    r"\b(co[- ])?founder\b",
    r"\bgeneral\s+manager\b",
    r"\b(?:third|second|fourth|fifth|sixth)\s+generation",
    r"\b\d(?:st|nd|rd|th)\s+generation\b",
    r"\bfamily[- ]owned\b",
    r"\bfamily[- ]operated\b",
    r"\bnonprofit\b",
    r"\bmunicipal(ly)?\s+owned\b",
    r"\bestablished\s+(?:in\s+)?\d{4}\b",
    r"\bsince\s+\d{4}\b",
    r"\b(grandfather|grandmother|father|mother|son|daughter|grandson|granddaughter)\b",
    r"\bcontinues\s+the\s+legacy\b",
    r"\bcarrying\s+on\s+the\s+legacy\b",
    r"\bover\s+\d{2,3}\s+years\b",
    r"\bmore\s+than\s+\d{2,3}\s+years\b",
]


def check_family_owner_story(home_html, base_url):
    """Pass if the About page names actual ownership / management figures
    OR establishes a clear long-standing operating history."""
    about_url = (
        find_internal_link(home_html, base_url, ABOUT_URL_KEYWORDS)
        or find_internal_link_by_path(home_html, base_url, ABOUT_PATH_FALLBACKS)
    )
    if not about_url:
        about_url = base_url

    page_html, status, _ = fetch_page(about_url, timeout=10)
    if not page_html or not status or status >= 400:
        if about_url != base_url:
            page_html = home_html
        else:
            return False

    text = re.sub(r"<[^>]+>", " ", page_html or "").lower()
    text = re.sub(r"\s+", " ", text)
    hits = 0
    for pat in FAMILY_OWNER_SIGNALS:
        if re.search(pat, text):
            hits += 1
            if hits >= 2:
                return True
    return False


# ----------------------------- 4. Preneed contact form -----------------------------

PRENEED_URL_KEYWORDS = [
    "/pre-need", "/preneed", "/pre-arrangement", "/pre-arrange",
    "/prearrange", "/pre-plan", "/preplan", "/pre-planning", "/preplanning",
    "/plan-ahead", "/planahead", "/planning-ahead", "/advance-planning",
    "/funeral-planning", "/cremation-planning", "/burial-planning",
    "/schedule-tour", "/property-tour", "/tour", "/request-tour",
    "/request-info", "/contact-us", "/get-info",
]
PRENEED_PATH_FALLBACKS = [
    "/preplanning", "/pre-planning", "/preneed", "/pre-need",
    "/plan-ahead", "/pre-arrangement", "/pre-arrangements",
    "/burial-planning", "/schedule-tour", "/tour",
]
PRENEED_FORM_HINTS = [
    "preneed", "pre-need", "pre-plan", "preplan", "pre-arrange",
    "prearrange", "pre-planning", "preplanning", "advance planning",
    "burial planning", "plan ahead", "planning ahead", "schedule a tour",
    "schedule a property tour", "request a tour", "tour our property",
]
SCHEDULING_HINTS = [
    "calendly.com", "acuityscheduling", "squareup.com/appointments",
    "jotform.com", "gravityforms", "wpforms", "wpcf7", "contact-form-7",
    "hubspot.com/forms", "hsforms.com", "typeform.com", "ninjaforms",
    "formstack", "fluentform", "wsform", "fluent-form", "gform_wrapper",
    "elfsight-app-form",
]


def check_preneed_form(home_html, base_url):
    """Pass if the site has a preneed / property tour page with a real
    form, OR the homepage itself has a prominent preneed CTA."""
    pn_url = (
        find_internal_link(home_html, base_url, PRENEED_URL_KEYWORDS)
        or find_internal_link_by_path(home_html, base_url, PRENEED_PATH_FALLBACKS)
    )
    if not pn_url:
        # Last-resort: look for preneed CTA copy on the homepage itself.
        text = re.sub(r"<[^>]+>", " ", home_html or "").lower()
        if any(h in text for h in PRENEED_FORM_HINTS):
            # And homepage has a real form too
            forms = re.findall(r"<form\b[^>]*>(.*?)</form>", home_html, re.IGNORECASE | re.DOTALL)
            for form in forms:
                form_low = form.lower()
                if 'role="search"' in form_low or 'type="search"' in form_low:
                    continue
                inputs = re.findall(r"<(input|textarea|select)\b[^>]*>", form, re.IGNORECASE)
                hidden = len(re.findall(r'<input[^>]+type=["\']hidden["\']', form, re.IGNORECASE))
                submit = len(re.findall(r'<input[^>]+type=["\']submit["\']', form, re.IGNORECASE))
                real_inputs = len(inputs) - hidden - submit
                if real_inputs >= 3:
                    return True
        return False

    page_html, status, _ = fetch_page(pn_url, timeout=10)
    if not page_html or not status or status >= 400:
        return False
    page_lower = page_html.lower()

    for h in SCHEDULING_HINTS:
        if h in page_lower:
            return True

    forms = re.findall(r"<form\b[^>]*>(.*?)</form>", page_html, re.IGNORECASE | re.DOTALL)
    for form in forms:
        form_low = form.lower()
        if 'role="search"' in form_low or 'type="search"' in form_low:
            continue
        if 'class="searchform' in form_low or 'id="searchform' in form_low:
            continue
        inputs = re.findall(r"<(input|textarea|select)\b[^>]*>", form, re.IGNORECASE)
        hidden = len(re.findall(r'<input[^>]+type=["\']hidden["\']', form, re.IGNORECASE))
        submit = len(re.findall(r'<input[^>]+type=["\']submit["\']', form, re.IGNORECASE))
        real_inputs = len(inputs) - hidden - submit
        if real_inputs >= 3:
            return True

    text = re.sub(r"<[^>]+>", " ", page_html).lower()
    pn_hits = sum(1 for h in PRENEED_FORM_HINTS if h in text)
    if pn_hits >= 3:
        return True

    return False


# ----------------------------- 5. Property tour photos -----------------------------

# Pages that typically host property visuals on cemetery sites.
GALLERY_URL_KEYWORDS = [
    "/gallery", "/photos", "/photo-gallery", "/our-property",
    "/property", "/grounds", "/tour", "/virtual-tour", "/aerial",
    "/drone", "/sections", "/our-grounds", "/visit",
]
GALLERY_PATH_FALLBACKS = [
    "/gallery", "/photos", "/property", "/our-property", "/grounds",
    "/tour", "/virtual-tour",
]


def _count_inline_images(html):
    """Heuristic: count distinct image references on the page that look
    like real cemetery property shots. We strip out logos/headers/icons
    by filename hint and require sane minimum dimension cues if present."""
    imgs = re.findall(r'<img\b[^>]+src=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
    seen = set()
    keep = []
    for src in imgs:
        s = src.lower()
        if any(skip in s for skip in [
            "logo", "icon", "favicon", "header", "footer", "spinner",
            "loading", "avatar", "social", "wp-emoji",
        ]):
            continue
        if s.endswith((".svg", ".gif")):
            continue
        if s in seen:
            continue
        seen.add(s)
        keep.append(s)
    return len(keep)


def check_property_tour_photos(home_html, base_url):
    """Pass if there's a gallery / photos / virtual tour page with several
    images, OR the homepage itself has 6+ non-stock images on it."""
    gallery_url = (
        find_internal_link(home_html, base_url, GALLERY_URL_KEYWORDS)
        or find_internal_link_by_path(home_html, base_url, GALLERY_PATH_FALLBACKS)
    )
    if gallery_url:
        page_html, status, _ = fetch_page(gallery_url, timeout=10)
        if page_html and status and 200 <= status < 300:
            count = _count_inline_images(page_html)
            if count >= 4:
                return True

    # Fallback: rich homepage with many non-logo images is also acceptable.
    if home_html:
        home_count = _count_inline_images(home_html)
        # Require both a respectable image count AND that the page passes
        # the stock-photo screen, otherwise we'd false-positive on stock-
        # heavy homepages.
        if home_count >= 8 and check_real_photos(home_html):
            return True
    return False


# ----------------------------- 6. Inventory / availability info -----------------------------

# Cemetery offerings -- vague sites mention none of these. Strong sites
# cover several.
INVENTORY_TERMS = [
    "burial plot", "burial plots", "single plot", "double plot",
    "family plot", "lawn crypt", "lawn crypts",
    "mausoleum", "mausoleum crypt", "private mausoleum",
    "columbarium", "columbarium niche", "columbarium niches",
    "cremation garden", "cremation gardens",
    "scatter garden", "scattering garden",
    "green burial", "natural burial",
    "veteran section", "veterans section",
    "infant section", "babyland",
    "memorial bench", "memorial benches",
    "marker", "markers", "monument", "monuments", "headstone",
    "above ground", "below ground",
]

INVENTORY_URL_KEYWORDS = [
    "/services", "/our-services", "/options", "/burial", "/cremation",
    "/mausoleum", "/columbarium", "/property", "/sections", "/products",
    "/what-we-offer", "/offerings",
]


def detect_inventory_offerings(html):
    """Return list of cemetery offerings found in the HTML."""
    if not html:
        return []
    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)
    found = []
    for term in INVENTORY_TERMS:
        if term in text and term not in found:
            found.append(term)
    return found


def check_inventory_info(home_html, base_url):
    """Pass if the site clearly explains 3+ distinct offerings. Looks at
    homepage AND a services-style sub-page if linked."""
    found = set(detect_inventory_offerings(home_html))

    # Pull in a services / options page if linked
    sub_url = find_internal_link(home_html, base_url, INVENTORY_URL_KEYWORDS)
    if sub_url:
        page_html, status, _ = fetch_page(sub_url, timeout=10)
        if page_html and status and 200 <= status < 300:
            found.update(detect_inventory_offerings(page_html))

    # Treat duplicates intelligently: "single plot" + "double plot" + "family plot"
    # all belong to the same "burial plot" bucket. Bucket distinct categories.
    buckets = {
        "plots": {"burial plot", "burial plots", "single plot", "double plot",
                  "family plot", "lawn crypt", "lawn crypts"},
        "mausoleum": {"mausoleum", "mausoleum crypt", "private mausoleum"},
        "columbarium": {"columbarium", "columbarium niche", "columbarium niches"},
        "cremation_garden": {"cremation garden", "cremation gardens",
                             "scatter garden", "scattering garden"},
        "green_burial": {"green burial", "natural burial"},
        "specialty_sections": {"veteran section", "veterans section",
                               "infant section", "babyland"},
        "markers": {"marker", "markers", "monument", "monuments", "headstone",
                    "memorial bench", "memorial benches"},
    }

    distinct_buckets = sum(1 for terms in buckets.values() if found & terms)
    return distinct_buckets >= 3, sorted(found)


# ----------------------------- 7. Property map / sections -----------------------------

PROPERTY_MAP_URL_KEYWORDS = [
    "/map", "/property-map", "/cemetery-map", "/section-map",
    "/sections", "/find-a-grave", "/grave-locator", "/grave-finder",
    "/locate-grave",
]
PROPERTY_MAP_PATH_FALLBACKS = [
    "/map", "/property-map", "/cemetery-map", "/sections", "/grave-finder",
]
PROPERTY_MAP_HINTS = [
    "property map", "cemetery map", "section map", "interactive map",
    "grave finder", "grave locator", "find a grave", "locate a grave",
    "section finder", "sections of the property",
]


def check_property_map(home_html, base_url):
    """Pass if the site has a property map / section finder / grave
    locator linked from the homepage."""
    if not home_html:
        return False
    text = re.sub(r"<[^>]+>", " ", home_html).lower()
    for h in PROPERTY_MAP_HINTS:
        if h in text:
            return True
    map_url = (
        find_internal_link(home_html, base_url, PROPERTY_MAP_URL_KEYWORDS)
        or find_internal_link_by_path(home_html, base_url, PROPERTY_MAP_PATH_FALLBACKS)
    )
    return bool(map_url)


# ----------------------------- 8. LocalBusiness schema -----------------------------

SCHEMA_TARGET_TYPES = [
    "LocalBusiness", "Cemetery", "Crematorium", "FuneralHome",
    "ProfessionalService", "EmergencyService",
]


def check_local_business_schema(html):
    """Look for application/ld+json blocks containing LocalBusiness / Cemetery."""
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        block = m.group(1)
        for t in SCHEMA_TARGET_TYPES:
            if f'"{t}"' in block or f"'{t}'" in block:
                return True
    return False


# ----------------------------- 9. Google reviews widget -----------------------------

REVIEWS_WIDGET_HINTS = [
    "elfsight.com", "elfsight-app",
    "trustindex.io", "trustindex",
    "sociablekit",
    "reviewsonmywebsite.com",
    "embedreviews", "embedsocial",
    "tagembed.com", "widget-tagembed",
    "shapo.io",
    "famewall",
    "google-reviews-widget", "googlereviewswidget",
    "g-reviews-widget",
    "widget.reviewsforce",
    "rwgmaps",
    "trustpulse",
    "reputationmanager", "reviewbuilder",
]


def check_google_reviews_widget(html):
    html_lower = html.lower()
    for h in REVIEWS_WIDGET_HINTS:
        if h in html_lower:
            return True
    return False


# ----------------------------- platform detection -----------------------------

# Cemetery website platforms. Detected via fingerprints in the HTML.
PLATFORM_FINGERPRINTS = [
    ("CemSites", [
        "cemsites.com", "cem-sites", "cemsitescdn",
    ]),
    ("Pontem", [
        "pontemsoftware.com", "pontem.com", "pontemcdn",
    ]),
    ("Buoh", [
        "buoh.com", "buohstatic",
    ]),
    ("Webcemeteries", [
        "webcemeteries.com", "webcem-cdn",
    ]),
    ("Frazer Cemetery", [
        "frazerconsultants.com/cemetery", "frazercemetery",
    ]),
    ("FuneralOne", [
        "funeralone.com", "f1edge",
    ]),
    ("Tukios", [
        "tukios.com", "tukioswebsites",
    ]),
    ("CFS", [
        "cfsmemorial.com", "consolidatedfuneralservices.com",
    ]),
    ("Gather", [
        "gather.com", "gather-cdn",
    ]),
    ("Squarespace", [
        "squarespace.com", "static.squarespace.com",
    ]),
    ("WordPress", [
        "wp-content/", "wp-includes/", "/wp-json/",
    ]),
    ("Wix", [
        "wix.com", "wixstatic.com",
    ]),
]


def detect_platform(html):
    """Return platform name string, or 'Unknown' if no match."""
    if not html:
        return "Unknown"
    html_lower = html.lower()
    for name, fingerprints in PLATFORM_FINGERPRINTS:
        for fp in fingerprints:
            if fp in html_lower:
                return name
    return "Unknown"


# ----------------------------- grading -----------------------------


def grade_website(checks):
    """A=8/8, B=6-7, C=3-5, D=1-2, F=0. None values are excluded and the
    threshold is scaled proportionally."""
    real = [(k, v) for k, v in checks.items() if v is not None]
    if not real:
        return "F"
    passed = sum(1 for _, v in real if v)
    total = len(real)
    scaled = round(passed * 8 / total)
    if scaled >= 8:
        return "A"
    if scaled >= 6:
        return "B"
    if scaled >= 3:
        return "C"
    if scaled >= 1:
        return "D"
    return "F"


# ----------------------------- main entry -----------------------------


def audit(url):
    if not url:
        return {
            "url": "",
            "error": "no url provided",
            "checks": {},
            "grade": "F",
        }

    html, status, final_url = fetch_page(url)
    if html is None:
        return {
            "url": url,
            "error": f"fetch failed: {final_url}",
            "checks": {},
            "grade": "F",
        }
    if status and status >= 400:
        return {
            "url": url,
            "error": f"HTTP {status}",
            "checks": {},
            "grade": "F",
        }

    base_url = base_origin(final_url)
    api_key = get_google_api_key()

    with ThreadPoolExecutor(max_workers=6) as ex:
        psi_future = ex.submit(check_pagespeed, final_url, api_key)
        family_future = ex.submit(check_family_owner_story, html, base_url)
        preneed_future = ex.submit(check_preneed_form, html, base_url)
        gallery_future = ex.submit(check_property_tour_photos, html, base_url)
        inv_future = ex.submit(check_inventory_info, html, base_url)
        map_future = ex.submit(check_property_map, html, base_url)

        psi = psi_future.result()
        family_pass = family_future.result()
        preneed_pass = preneed_future.result()
        gallery_pass = gallery_future.result()
        inv_pass, inv_offerings = inv_future.result()
        map_pass = map_future.result()

    # 8 graded checks. Property map is reported but graded as part of
    # the same set so the prospect sees it on the scorecard. (We chose to
    # include it in the grading set because a missing map is a real gap.)
    checks = {
        "real_photos": check_real_photos(html),
        "pagespeed_mobile": psi.get("pass"),
        "family_owner_story": family_pass,
        "preneed_form": preneed_pass,
        "localbusiness_schema": check_local_business_schema(html),
        "google_reviews_widget": check_google_reviews_widget(html),
        "property_tour_photos": gallery_pass,
        "inventory_info": inv_pass,
    }

    return {
        "url": final_url,
        "status": status,
        "checks": checks,
        # Property map: surfaced separately, not part of the 8/8 grade so
        # we don't punish small cemeteries that haven't built a section
        # finder yet. Still shown on the PDF as a data point.
        "property_map": map_pass,
        "pagespeed_score": psi.get("score"),
        "pagespeed_error": psi.get("error"),
        "inventory_offerings": inv_offerings,
        "platform": detect_platform(html),
        "grade": grade_website(checks),
    }


def main():
    parser = argparse.ArgumentParser(description="Cemetery website audit (hard mode)")
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.url), indent=2))


if __name__ == "__main__":
    main()
