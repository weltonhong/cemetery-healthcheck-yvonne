"""
Trade Show Online Health Check - Cemetery Edition

Fast (60-90 second) online presence audit for a cemetery prospect.
Designed for live use at a cemetery industry convention or for
cold-outreach prep: prints results to terminal as each check
completes, then generates a branded one-page Ring Ring Marketing PDF.

Cemeteries operate on a preneed-dominant model. The vocabulary and
search buckets reflect that: "cemetery [city]" is the general at-need
+ preneed search; "cemetery plots [city]" is the high-intent preneed-
buyer search.

Runs all checks in parallel:
  1. Google Reviews + top competitor (Google Places API)
  2. Google 3-Pack from each user-supplied city, plus a "cemetery plots"
     3-pack from the home city
  3. SEO organic ranking from each city ("cemetery [city] [state]")
     plus a "cemetery plots" ranking from the home city
  4. Website audit (homepage scrape + cemetery-specific heuristics)
  5. Reviews snapshot (Google from Places, FB/Yelp via search)
  6. Competitor ads check from each bucket's SERP HTML

Usage:
    python health_check.py "Forest Lawn Memorial Park" "Glendale" "CA" ["Burbank"] ["Pasadena"]

Required: business, home_city, state. Second/third cities are optional
but encouraged (cemeteries draw from a wide service radius).
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# Force UTF-8 on stdout/stderr.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Local
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import website_audit  # noqa: E402
import name_matcher  # noqa: E402


PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

PLACES_FIELD_MASK = (
    "places.displayName,"
    "places.formattedAddress,"
    "places.rating,"
    "places.userRatingCount,"
    "places.businessStatus,"
    "places.websiteUri,"
    "places.googleMapsUri"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ----------------------------- cemetery vs directory filter -----------------------------

# Find A Grave is the dominant cemetery-vertical SERP polluter -- it appears
# for nearly every "cemetery [city]" query and is NOT a real cemetery
# website, just a memorialization aggregator. Plus the standard non-vertical
# directory / aggregator list.
DIRECTORY_DOMAINS = {
    # Cemetery-vertical aggregators / memorialization platforms
    "findagrave.com", "billiongraves.com", "interment.net",
    "cemeteries.com", "cemeterytours.com", "cemeteryregistry.us",
    "usgwarchives.net", "ancestry.com", "familysearch.org",
    "rootsweb.com", "mygenealogyhound.com",
    # Obit aggregators that bleed into cemetery searches
    "legacy.com", "tributes.com", "ever-loved.com", "everloved.com",
    "tributearchive.com",
    # National cemetery operator parent portals (the local property page is
    # fine, the parent corporate index is a directory listing)
    "stonemor.com", "dignitymemorial.com", "sci-corp.com",
    "carriageservices.com", "parklawncorp.com", "foundationpartners.com",
    # Funeral / cremation directories that occasionally outrank cemeteries
    "funeralocity.com", "funerals360.com", "funeralhomes.com",
    # Government / nonprofit info hubs
    "icfa.org", "nccafuneral.org", "cana-cremation.org", "cdc.gov",
    "hhs.gov", "va.gov", "ssa.gov", "nih.gov", "cem.va.gov",
    # Health information sites
    "healthline.com", "webmd.com", "verywellhealth.com",
    # Review aggregators / business directories
    "yelp.com", "bbb.org", "yellowpages.com", "whitepages.com", "manta.com",
    "expertise.com", "threebestrated.com", "angi.com", "angieslist.com",
    "thumbtack.com", "homeadvisor.com", "consumeraffairs.com", "trustpilot.com",
    "tripadvisor.com",
    # Social and Q&A
    "facebook.com", "linkedin.com", "youtube.com", "instagram.com",
    "twitter.com", "x.com", "reddit.com", "quora.com", "nextdoor.com",
    "pinterest.com", "tiktok.com",
    # Job boards
    "indeed.com", "glassdoor.com", "ziprecruiter.com", "monster.com",
    # Reference / encyclopedia
    "wikipedia.org",
    # News / city-listing aggregators
    "city-data.com", "yellowbook.com",
}

# Title patterns that indicate informational / blog / listicle / how-to
# content rather than an actual cemetery homepage.
INFO_TITLE_PATTERNS = [
    r"^how\s",
    r"^what\s",
    r"^why\s",
    r"^when\s",
    r"^where\s",
    r"^which\s",
    r"\bwhat is\b",
    r"\bwhat are\b",
    r"\bvs\.?\s",
    r"\s\bvs\b\s",
    r"\bcost of\b",
    r"\bcost in\b",
    r"\bhow much\b",
    r"\bguide to\b",
    r"\bguide\s*$",
    r"\bexplained\b",
    r"\bdifference between\b",
    r"\b\d{4}\s+(income|asset|guide|update|rates?)",
    r"\bchecklist\b",
    r"\bfaq\b",
    r"\bdefinition\b",
    r"\bbenefits of\b",
    r"\btypes of\b",
    # Listicles
    r"\btop\s+\d+\b",
    r"\bbest\s+\d+\b",
    r"\b\d+\s+best\b",
    r"\bthe\s+best\s+\d+",
    r"^the\s+\d+\s+best\b",
    r"\bbest\s+(cemetery|cemeteries|memorial)\b",
    r"\bbest of\b",
    r"\breviews?\s+of\b",
    r"^top\s+(cemetery|cemeteries|memorial)",
    r"^best\s+(cemetery|cemeteries|memorial)",
    r"\b(cemetery|cemeteries|memorial)\s+(parks?|gardens?|providers?)\s+in\b",
    # Memorial / grave finder pages, not businesses
    r"\bfind\s+a\s+grave\b",
    r"\bgrave\s+(finder|locator|search)\b",
]


# Generic vocabulary that doesn't identify a real cemetery brand.
GENERIC_TITLE_WORDS = {
    "cemetery", "cemeteries", "memorial", "memorials", "park", "parks",
    "garden", "gardens", "lawn", "hill", "hills", "ridge", "valley",
    "grove", "meadow", "view", "vista", "rest", "peace", "eternal",
    "mausoleum", "columbarium", "burial", "interment", "plot", "plots",
    "service", "services", "and", "of", "the", "in", "for", "with",
    "best", "trusted", "your", "our", "professional", "co", "inc", "llc",
    "wa", "ca", "az", "fl", "tx", "ny", "co", "nv",
}


def is_generic_title(title):
    if not title:
        return True
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", title).lower()
    words = [w for w in cleaned.split() if w]
    if not words:
        return True
    non_generic = [w for w in words if w not in GENERIC_TITLE_WORDS and len(w) >= 3]
    return len(non_generic) == 0


# Atomic word dictionary for splitting concatenated cemetery domain names.
_DOMAIN_WORD_SPLITS = sorted([
    "cemetery", "cemeteries", "memorial", "memorials", "park", "parks",
    "garden", "gardens", "lawn", "hill", "hills", "ridge", "valley",
    "grove", "meadow", "view", "vista", "rest", "peace", "eternal",
    "mausoleum", "columbarium", "burial", "and", "of", "the", "for",
    "at", "my", "your", "our", "best", "memorial", "tribute", "tributes",
    "celebration", "life", "harbor", "stone", "stones", "marker",
    "markers", "gate", "gates", "haven", "fields", "field", "mountain",
    "oak", "pine", "elm", "willow", "rose", "lily", "lake", "river",
    "spring", "springs", "saint", "holy", "sacred",
],
    key=len, reverse=True,
)

_SHORT_PARTICLES = {"at", "of", "my"}

# Minimum residual stub length when peeling vocabulary words off a
# concatenated domain. Prevents 'forestlawn' -> 'fo|rest|lawn' just
# because 'rest' and 'lawn' both happen to be in the dictionary.
_MIN_STUB_LEN = 3


def humanize_domain(domain):
    """Convert 'forest-lawn.com' -> 'Forest Lawn'. Splits camelCase-ish
    concatenated cemetery domains using a greedy word dictionary, with
    a minimum-stub guard so short residuals like 'fo' don't slip through.
    """
    if not domain:
        return ""
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    host = domain.split("/")[0]
    parts = host.split(".")
    sld = parts[-2] if len(parts) >= 2 else parts[0]
    pieces = [p for p in re.split(r"[-_]", sld) if p]
    expanded = []
    for p in pieces:
        remaining = p.lower()
        found_any = True
        segments = []
        while remaining and found_any:
            found_any = False
            for word in _DOMAIN_WORD_SPLITS:
                if not remaining.endswith(word):
                    continue
                if len(remaining) < len(word):
                    continue
                stub_len = len(remaining) - len(word)
                # Guard 1: short particles need a sane stub length
                if word in _SHORT_PARTICLES and stub_len > 0 and stub_len < 3:
                    continue
                # Guard 2: don't leave a stub shorter than _MIN_STUB_LEN
                # unless the entire word consumes the input
                if stub_len > 0 and stub_len < _MIN_STUB_LEN:
                    continue
                segments.insert(0, word)
                remaining = remaining[: -len(word)]
                found_any = True
                break
        if remaining:
            segments.insert(0, remaining)
        expanded.extend(segments if segments else [p])
    return " ".join(p.capitalize() for p in expanded)


def display_name_from_result(result):
    """Return the humanized domain as the display name for an organic result."""
    domain = (result.get("domain") or "").strip()
    if domain:
        return humanize_domain(domain)
    return (result.get("title") or "").strip()


def is_real_cemetery_result(result):
    """Decide whether an organic SERP result looks like a real cemetery
    website (vs. Find A Grave, gov sites, info articles, etc.)."""
    domain = (result.get("domain") or "").lower()
    title = (result.get("title") or "").lower()

    if not domain:
        return False

    for bad in DIRECTORY_DOMAINS:
        if bad == domain or domain.endswith("." + bad):
            return False

    for pat in INFO_TITLE_PATTERNS:
        if re.search(pat, title):
            return False

    return True


# ----------------------------- helpers -----------------------------


def get_google_api_key():
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "[System.Environment]::GetEnvironmentVariable('GOOGLE_API_KEY', 'User')"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def fuzzy_name_match(a, b):
    if not a or not b:
        return False
    na = re.sub(r"[^a-z0-9 ]", "", a.lower()).strip()
    nb = re.sub(r"[^a-z0-9 ]", "", b.lower()).strip()
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    a_words = [w for w in na.split() if len(w) > 2]
    if a_words and all(w in nb for w in a_words):
        return True
    return False


def geocode(address, api_key):
    url = f"{GEOCODE_API_URL}?{urllib.parse.urlencode({'address': address, 'key': api_key})}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception:
        pass
    return None, None


def places_text_search(query, api_key, lat=None, lng=None, radius=15000, max_results=10):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    body = {"textQuery": query, "maxResultCount": max_results}
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius,
            }
        }
    body_bytes = json.dumps(body).encode("utf-8")
    try:
        req = urllib.request.Request(
            PLACES_API_URL, data=body_bytes, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def parse_places(data):
    out = []
    for p in data.get("places", []):
        out.append({
            "name": p.get("displayName", {}).get("text", ""),
            "address": p.get("formattedAddress", ""),
            "rating": p.get("rating"),
            "review_count": p.get("userRatingCount"),
            "status": p.get("businessStatus", ""),
            "website": p.get("websiteUri", ""),
            "maps_url": p.get("googleMapsUri", ""),
        })
    return out


# ----------------------------- check functions -----------------------------


def check_google_intel(business, city, state):
    """Wrap quick-intel/google_intel.py for target + competitor data."""
    repo_root = SCRIPT_DIR.parents[2]
    intel_script = repo_root / "my-skills" / "quick-intel" / "scripts" / "google_intel.py"
    try:
        result = subprocess.run(
            [
                sys.executable, str(intel_script),
                "--business", business,
                "--city", city,
                "--state", state,
                "--vertical", "cemetery",
            ],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "google_intel failed"}
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


# ----------------------------- buckets -----------------------------

# A "bucket" is one (keyword, geo-city) pair that gets its own SERP fetch.
# Cemetery is the primary search intent; "cemetery plots" is the preneed-
# buyer search and we run it in the home city only as the high-intent
# preneed signal.

def build_buckets(cities, state):
    """Return list of (label, query, geo_city) tuples."""
    buckets = []
    home_city = cities[0]
    for c in cities:
        label = f"cemetery / {c}"
        query = f"cemetery {c} {state}"
        buckets.append((label, query, c))
    label = f"cemetery plots / {home_city}"
    query = f"cemetery plots {home_city} {state}"
    buckets.append((label, query, home_city))
    return buckets


def build_pack_from_seo(buckets, seo_per_bucket):
    """Derive 3-Pack results from the local_pack data already parsed out of
    each bucket's Google SERP."""
    out = {"buckets": [b[0] for b in buckets], "results": {}}
    for label, _, _ in buckets:
        d = seo_per_bucket.get(label) or {}
        lp = d.get("local_pack") or {}
        out["results"][label] = {
            "rank": lp.get("rank"),
            "in_3_pack": bool(lp.get("in_3_pack")),
            "top_3": lp.get("top_3") or [],
        }
    return out


def ddg_html_search(query):
    """DuckDuckGo HTML search; returns list of {title, url}."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        html = r.text
    except Exception:
        return []
    results = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if "uddg=" in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = qs.get("uddg", [href])[0]
        results.append({"title": title, "url": href})
        if len(results) >= 15:
            break
    return results


def check_seo_per_bucket(business, website, buckets):
    """For each bucket, run the SERP rank script with that bucket's query."""
    biz_domain = ""
    if website:
        try:
            biz_domain = urllib.parse.urlparse(
                website if website.startswith("http") else "https://" + website
            ).netloc.lower().replace("www.", "")
        except Exception:
            biz_domain = ""

    serp_script = SCRIPT_DIR / "google_serp_rank.py"

    def run_one(bucket):
        label, query, geo_city = bucket
        try:
            result = subprocess.run(
                [
                    sys.executable, str(serp_script),
                    "--business", business,
                    "--domain", biz_domain,
                    "--city", geo_city,
                    "--queries", query,
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return label, {
                    "query": query, "rank": None, "top_3": [], "ads": [],
                    "error": result.stderr.strip()[:200] or "serp script failed",
                }
            data = json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            return label, {
                "query": query, "rank": None, "top_3": [], "ads": [],
                "error": "timeout",
            }
        except Exception as e:
            return label, {
                "query": query, "rank": None, "top_3": [], "ads": [],
                "error": str(e),
            }

        match = next(
            (x for x in data.get("queries", []) if x.get("query") == query), None
        )
        if not match:
            return label, {
                "query": query, "rank": None, "top_3": [], "ads": [],
                "error": "no result",
            }
        if match.get("error"):
            return label, {
                "query": query, "rank": None, "top_3": [],
                "ads": match.get("ads") or [],
                "error": match["error"],
            }
        raw_results = match.get("results") or []
        print(f"[DEBUG SEO {label}] raw results count: {len(raw_results)}")
        for i, r in enumerate(raw_results[:6]):
            print(
                f"[DEBUG SEO {label}] #{i+1}: "
                f"domain={r.get('domain')!r} "
                f"title={(r.get('title') or '')[:80]!r}"
            )
        sys.stdout.flush()

        # Filter to real cemetery websites only -- skip directories,
        # Find A Grave, info articles, gov sites.
        top_3 = []
        seen_names = set()
        for r in raw_results:
            if is_real_cemetery_result(r):
                name = display_name_from_result(r)
                key = name.lower().strip() if name else ""
                print(
                    f"[DEBUG SEO {label}] KEEP domain={r.get('domain')!r} "
                    f"-> display_name={name!r}"
                )
                if name and key not in seen_names:
                    seen_names.add(key)
                    top_3.append(name)
                    if len(top_3) >= 3:
                        break
        sys.stdout.flush()

        raw_ads = match.get("ads") or []
        print(f"[DEBUG ADS {label}] raw ads count: {len(raw_ads)}")
        for i, a in enumerate(raw_ads[:8]):
            print(
                f"[DEBUG ADS {label}] #{i+1}: "
                f"name={a.get('name')!r} domain={a.get('domain')!r}"
            )
        sys.stdout.flush()

        return label, {
            "query": query,
            "rank": match.get("rank"),
            "top_3": top_3,
            "ads": raw_ads,
            "local_pack": match.get("local_pack") or {
                "rank": None, "in_3_pack": False, "top_3": []
            },
        }

    out = {}
    with ThreadPoolExecutor(max_workers=max(1, len(buckets))) as ex:
        futures = [ex.submit(run_one, b) for b in buckets]
        for f in as_completed(futures):
            label, data = f.result()
            out[label] = data
    return out


def check_website(website):
    if not website:
        return {
            "error": "no website on Google listing",
            "checks": {},
            "grade": None,
            "unverified": True,
            "unverified_reason": "No website listed on Google profile",
        }
    result = website_audit.audit(website)
    err = (result.get("error") or "").lower()
    is_blocked = (
        "403" in err
        or "timeout" in err
        or "fetch failed" in err
        or "ssl" in err
        or err.startswith("http 4")
        or err.startswith("http 5")
    )
    if is_blocked or (result.get("error") and not result.get("checks")):
        result["grade"] = None
        result["unverified"] = True
        result["unverified_reason"] = "Website blocked our scan"
    return result


def check_reviews_snapshot(business, city, state, google_data):
    """Pull review counts from Google (already have it) + try FB and Yelp."""
    snapshot = {
        "google": {
            "count": (google_data.get("target") or {}).get("review_count"),
            "rating": (google_data.get("target") or {}).get("rating"),
        },
        "facebook": {"count": None, "rating": None, "url": ""},
        "yelp": {"count": None, "rating": None, "url": ""},
    }

    fb_results = ddg_html_search(f'"{business}" {city} {state} site:facebook.com')
    for r in fb_results[:5]:
        if "facebook.com" in r["url"] and "/pages" not in r["url"]:
            snapshot["facebook"]["url"] = r["url"]
            break

    yelp_results = ddg_html_search(f'"{business}" {city} {state} site:yelp.com')
    for r in yelp_results[:5]:
        if "yelp.com/biz" in r["url"]:
            snapshot["yelp"]["url"] = r["url"]
            m = re.search(r"(\d+)\s+reviews?", r["title"], re.IGNORECASE)
            if m:
                snapshot["yelp"]["count"] = int(m.group(1))
            break

    return snapshot


def _strict_name_match(target, candidate):
    """Strict business-name comparison for ad-vs-competitor matching."""
    def norm(s):
        s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
        s = re.sub(r"\s+", " ", s).strip()
        for suf in (" llc", " inc", " corp", " co", " ltd"):
            if s.endswith(suf):
                s = s[: -len(suf)]
        return s

    a = norm(target)
    b = norm(candidate)
    if not a or not b:
        return False
    if len(a) < 5 or len(b) < 5:
        return False
    return a in b or b in a


# Words that don't distinguish a local cemetery from its parent operator
# brand or generic vertical vocabulary. National cemetery operators use
# corporate brand names (StoneMor, SCI/Dignity, Carriage) and we should
# NOT attribute their ads to local cemeteries that share generic words.
FRANCHISE_STOPWORDS = {
    # Generic cemetery / vertical vocabulary
    "cemetery", "cemeteries", "memorial", "memorials", "park", "parks",
    "garden", "gardens", "lawn", "hill", "hills", "ridge", "valley",
    "grove", "meadow", "view", "vista", "rest", "peace", "eternal",
    "mausoleum", "columbarium", "burial", "interment", "plot", "plots",
    "service", "services", "professional", "trusted", "premier", "preferred",
    # National cemetery operators (parent brand portion only)
    "stonemor", "stonemorpartners", "sci", "dignity", "carriage", "stewart",
    "everstory", "foundation", "partners", "parklawn",
    # Connectors / corporate suffixes
    "in", "of", "the", "and", "for", "to", "with", "at", "by", "on",
    "co", "inc", "llc", "corp", "ltd", "company", "limited", "group",
    # Direction qualifiers too common to be distinctive alone
    "north", "south", "east", "west", "central", "greater", "metro",
    "area", "region", "regional", "county",
}


def distinctive_tokens(name):
    """Return tokens that distinguish a local cemetery from generic
    vocabulary or parent-operator brands."""
    if not name:
        return set()
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    distinctive = [t for t in tokens if t not in FRANCHISE_STOPWORDS and len(t) >= 3]
    if distinctive:
        return set(distinctive)
    return set(t for t in tokens if len(t) >= 4)


CONNECTOR_TOKENS = {
    "of", "the", "and", "for", "in", "to", "at", "by", "on",
    "a", "an", "with", "from", "or",
    "co", "inc", "llc", "corp", "ltd", "company", "limited", "group",
    "md", "wa", "ca", "az", "fl", "tx", "ny", "co", "nv", "wi", "va",
    "or", "il", "ga", "nc", "sc", "tn", "ky", "oh", "pa", "nj", "ma",
    "mn", "mi", "mo", "ks", "ne", "ia", "in", "ar", "la", "ms", "al",
}


def normalize_domain(d):
    """Strip protocol, www, and path; return lowercase host or empty."""
    if not d:
        return ""
    d = d.strip().lower()
    d = re.sub(r"^https?://", "", d)
    if d.startswith("www."):
        d = d[4:]
    d = d.split("/")[0].split("?")[0]
    return d


def build_ads_per_bucket(business, competitors, seo_per_bucket, prospect_website=""):
    """For each bucket, derive ads info from that bucket's SERP ad block.

    Prospect-as-running detection: ONLY match if the ad's display domain
    equals the prospect's actual website domain. National operator ads
    (StoneMor, SCI, Carriage corporate domains) do NOT count as the local
    cemetery running ads, because the local manager is not paying for them.
    """
    prospect_domain = normalize_domain(prospect_website)

    out = {}
    for label, data in seo_per_bucket.items():
        ads_list = data.get("ads") or []

        names = []
        seen = set()
        for adv in ads_list:
            name = (adv or {}).get("name", "")
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)

        prospect_match = None
        # 1) Domain-only match: highest precision. Corporate operator ads
        # using a parent domain (StoneMor, SCI/Dignity, etc.) won't match
        # the local cemetery's domain.
        if prospect_domain:
            for adv in ads_list:
                ad_domain = normalize_domain((adv or {}).get("domain", ""))
                if ad_domain and ad_domain == prospect_domain:
                    prospect_match = (adv or {}).get("name", ad_domain)
                    break
        # 2) Name-based fallback: many SERP scrapers fail to extract the
        # advertiser's display domain, leaving the domain field empty.
        # Without a name fallback the scorecard prints "Not running" even
        # when the prospect's name is sitting in the ad block. The
        # normalized matcher handles deathcare suffix variations
        # (e.g. "Holy Cross Cemetery" vs "Holy Cross Catholic Cemetery").
        if not prospect_match and business:
            for adv in ads_list:
                adv_name = (adv or {}).get("name", "")
                if not adv_name:
                    continue
                if name_matcher.name_matches(business, adv_name):
                    prospect_match = adv_name
                    break

        comp_hits = []
        seen_matches = set()
        for comp in (competitors or [])[:5]:
            comp_name = (comp.get("name") or "").strip()
            if not comp_name:
                continue
            for n in names:
                if _strict_name_match(comp_name, n) and n.lower() not in seen_matches:
                    comp_hits.append({"name": comp_name, "matched_as": n})
                    seen_matches.add(n.lower())
                    break

        out[label] = {
            "prospect_running_ads": bool(prospect_match),
            "prospect_match": prospect_match,
            "all_advertisers": names,
            "competitors_running_ads": comp_hits,
        }
    return out


# ----------------------------- grading -----------------------------


def grade_reviews_cemetery(target_count, comp_count=0):
    """Cemetery-specific grading scale. Cemeteries get far fewer reviews
    than service-business verticals because plot buyers don't typically
    leave reviews like service experiences do.

        A = more reviews than the top competitor, OR 30+ total
        B = 15-29
        C = 5-14
        D = 1-4
        F = 0
    """
    if target_count is None:
        return "F"
    if (comp_count and target_count > comp_count) or target_count >= 30:
        return "A"
    if target_count >= 15:
        return "B"
    if target_count >= 5:
        return "C"
    if target_count >= 1:
        return "D"
    return "F"


def grade_count_based(found, total):
    """A=found in all, B=found in most (>1 but not all), C=found in 1, F=none."""
    if total == 0:
        return "F"
    if found == 0:
        return "F"
    if found == total:
        return "A"
    if found == 1:
        return "C"
    return "B"


def grade_3pack_multi(pack):
    results = pack.get("results") or {}
    buckets = pack.get("buckets") or list(results.keys())
    total = len(buckets)
    found = sum(1 for b in buckets if (results.get(b) or {}).get("in_3_pack"))
    return grade_count_based(found, total)


def grade_seo_multi(seo_per_bucket):
    buckets = list(seo_per_bucket.keys())
    total = len(buckets)
    found = 0
    for b in buckets:
        rank = (seo_per_bucket.get(b) or {}).get("rank")
        if rank is not None and rank <= 10:
            found += 1
    return grade_count_based(found, total)


def grade_ads_multi(ads_per_bucket):
    buckets = list(ads_per_bucket.keys())
    total = len(buckets)
    found = sum(
        1 for b in buckets if (ads_per_bucket.get(b) or {}).get("prospect_running_ads")
    )
    return grade_count_based(found, total)


def overall_grade(grades):
    """Average of grades, ignoring None values."""
    pts = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    inv = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}
    real = [g for g in grades if g in pts]
    if not real:
        return "F"
    avg = round(sum(pts[g] for g in real) / len(real))
    return inv.get(avg, "F")


# ----------------------------- printing -----------------------------


def print_header(business, city, state):
    title = f"ONLINE HEALTH CHECK | {business} {city}, {state}"
    bar = "=" * max(60, len(title) + 4)
    print()
    print(bar)
    print(title)
    print(bar)
    print()
    sys.stdout.flush()


def print_section(label, body):
    print(f"{label}")
    for line in body:
        print(f"  {line}")
    print()
    sys.stdout.flush()


# ----------------------------- main -----------------------------


def run_health_check(business, cities, state):
    """cities: list of city names (1-3). First entry is the home city."""
    api_key = get_google_api_key()
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in environment.")
        sys.exit(1)

    home_city = cities[0]
    print_header(business, home_city, state)
    started = time.time()

    buckets = build_buckets(cities, state)
    bucket_labels = [b[0] for b in buckets]

    results = {
        "business": business,
        "city": home_city,
        "cities": list(cities),
        "buckets": bucket_labels,
        "state": state,
        "vertical": "cemetery",
        "scanned_at": datetime.datetime.now().isoformat(),
    }

    print(f"Pulling Google data for {home_city}, {state}...")
    sys.stdout.flush()
    intel = check_google_intel(business, home_city, state)
    results["google_intel"] = intel
    target = intel.get("target") or {}
    competitors = intel.get("competitors") or []
    website = target.get("website", "")

    target_count = target.get("review_count")
    target_rating = target.get("rating")
    print_section(
        "GOOGLE REVIEWS:",
        [
            f"{target_count if target_count is not None else 'NOT FOUND'} reviews"
            f", {target_rating if target_rating is not None else '-'} stars"
        ],
    )

    if competitors:
        # Filter out the prospect itself from competitors before picking the top
        def _is_self(name):
            if not name or not business:
                return False
            return (business.lower() in name.lower()
                    or name.lower() in business.lower())
        real_comps = [c for c in competitors if not _is_self(c.get("name", ""))]
        if real_comps:
            top_comp = max(
                real_comps,
                key=lambda c: (c.get("review_count") or 0),
            )
            print_section(
                "TOP COMPETITOR:",
                [
                    f"{top_comp.get('name', '?')} -- "
                    f"{top_comp.get('review_count') or 0} reviews, "
                    f"{top_comp.get('rating') or '-'} stars"
                ],
            )
            results["top_competitor"] = top_comp
            gap = (top_comp.get("review_count") or 0) - (target_count or 0)
            if gap > 0:
                severity = "CRITICAL" if gap >= 100 else "SIGNIFICANT" if gap >= 30 else "MODERATE"
                print_section(
                    "REVIEW GAP:",
                    [f"{gap} reviews behind ({severity})"],
                )
                results["review_gap"] = gap
        else:
            print_section(
                "TOP COMPETITOR:",
                [f"Limited competition in {home_city} (no other cemeteries returned by Google)"],
            )
            results["limited_competition"] = True
    else:
        print_section(
            "TOP COMPETITOR:",
            [f"Limited competition in {home_city} (no other cemeteries returned by Google)"],
        )
        results["limited_competition"] = True

    print(
        f"Running parallel scans (SEO+3-Pack, Website, Reviews) "
        f"across {len(buckets)} buckets: {', '.join(bucket_labels)}\n"
    )
    sys.stdout.flush()

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(check_seo_per_bucket, business, website, buckets): "seo",
            ex.submit(check_website, website): "website",
            ex.submit(check_reviews_snapshot, business, home_city, state, intel): "reviews",
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                results[name] = {"error": str(e)}

    results["3pack"] = build_pack_from_seo(buckets, results.get("seo", {}))

    # Print 3-Pack
    pack = results.get("3pack", {})
    pack_results = pack.get("results", {})
    label_width = max(len(b) for b in bucket_labels) + 4

    def fmt_pack_line(label):
        d = pack_results.get(label) or {}
        lab = f"{label}:"
        if not d or "error" in d:
            return f"{lab:<{label_width}} ERROR ({d.get('error', '?')})"
        top_3_list = d.get("top_3", []) or []
        if not top_3_list:
            return f"{lab:<{label_width}} No local map pack found for this bucket"
        top_3_str = ", ".join(top_3_list[:3])
        if d.get("in_3_pack"):
            return f"{lab:<{label_width}} FOUND rank {d['rank']} (Top 3: {top_3_str})"
        return f"{lab:<{label_width}} NOT FOUND (Top 3: {top_3_str})"

    pack_grade = grade_3pack_multi(pack)
    pack_lines = [fmt_pack_line(b) for b in bucket_labels]
    pack_lines.append(f"Grade: {pack_grade}")
    print_section("GOOGLE LOCAL MAP RANKINGS:", pack_lines)
    results["pack_grade"] = pack_grade

    # Print SEO
    seo = results.get("seo", {})
    seo_grade = grade_seo_multi(seo)

    def trim_title(t):
        t = (t or "").replace("&amp;", "&").replace("&#39;", "'") \
                     .replace("&quot;", '"').replace("&#x27;", "'")
        short = re.split(r"\s+[\|•:]\s+|\s+-\s+|\s+–\s+", t, maxsplit=1)[0].strip()
        return (short or t)[:60]

    seo_lines = []
    for b in bucket_labels:
        d = seo.get(b) or {}
        rank = d.get("rank")
        top_3 = d.get("top_3") or []
        cleaned = [trim_title(t) for t in top_3[:3] if t]
        if not cleaned:
            seo_lines.append(f"{b}: No organic results found for this bucket")
            continue
        top_3_str = ", ".join(cleaned)
        if rank is None:
            seo_lines.append(f"{b}: Not in top 10 (Top 3: {top_3_str})")
        else:
            seo_lines.append(f"{b}: Rank {rank} (Top 3: {top_3_str})")
    seo_lines.append(f"Grade: {seo_grade}")
    print_section("GOOGLE ORGANIC RANKINGS (SEO):", seo_lines)
    results["seo_grade"] = seo_grade

    # Build and print Google Ads per bucket (BEFORE Website)
    ads_per_bucket = build_ads_per_bucket(
        business, competitors, seo, prospect_website=website
    )
    results["ads"] = ads_per_bucket
    ads_grade = grade_ads_multi(ads_per_bucket)
    ads_lines = []
    business_running_anywhere = False
    for b in bucket_labels:
        d = ads_per_bucket.get(b) or {}
        if d.get("prospect_running_ads"):
            business_running_anywhere = True
        advs = d.get("all_advertisers") or []
        if advs:
            ads_lines.append(f"{b}: {', '.join(advs)}")
        else:
            # Cemetery-specific framing: no advertisers = open lane, not failure.
            ads_lines.append(f"{b}: No ads detected (open lane)")
    ads_lines.append(
        f"{business}: {'Running' if business_running_anywhere else 'Not running'}"
    )
    ads_lines.append(f"Grade: {ads_grade}")
    print_section("GOOGLE ADS:", ads_lines)
    results["ads_grade"] = ads_grade

    # Print Website
    web = results.get("website", {})
    if web.get("unverified"):
        reason = web.get("unverified_reason") or web.get("error") or "blocked"
        print_section("WEBSITE:", [
            f"Unable to verify -- {reason}",
            "Grade: not counted in overall",
        ])
        web_grade = None
    else:
        c = web.get("checks", {})

        def yn(v, true_label="Yes", false_label="No"):
            if v is True:
                return true_label
            if v is False:
                return false_label
            return "?"

        psi_score = web.get("pagespeed_score")
        if psi_score is None:
            psi_display = "Unable to test"
        else:
            psi_display = f"{psi_score}/100 " + ("(PASS)" if psi_score >= 50 else "(FAIL)")

        platform = web.get("platform") or "Unknown"
        inventory_offerings = web.get("inventory_offerings") or []
        inventory_display = (
            f"Yes ({', '.join(inventory_offerings[:5])})"
            if c.get("inventory_info") and inventory_offerings
            else ("Yes" if c.get("inventory_info") else "No")
        )
        # Property map is a non-graded data point at the top level of web
        property_map = web.get("property_map")

        web_lines = [
            f"Real photos:              {yn(c.get('real_photos'), 'Yes', 'No (stock detected)')}",
            f"PageSpeed mobile:         {psi_display}",
            f"Family/owner story:       {yn(c.get('family_owner_story'), 'Yes', 'No (generic About page)')}",
            f"Preneed contact form:     {yn(c.get('preneed_form'), 'Yes', 'No')}",
            f"LocalBusiness schema:     {yn(c.get('localbusiness_schema'), 'Yes', 'No')}",
            f"Google reviews widget:    {yn(c.get('google_reviews_widget'), 'Yes', 'No')}",
            f"Property tour photos:     {yn(c.get('property_tour_photos'), 'Yes', 'No (stock or sparse)')}",
            f"Inventory / availability: {inventory_display}",
            f"Property map:             {yn(property_map, 'Yes', 'No')}  (data point, not graded)",
            f"Platform:                 {platform}",
            f"Grade: {web.get('grade', 'F')}",
        ]
        print_section("WEBSITE:", web_lines)
        web_grade = web.get("grade", "F")
    results["website_grade"] = web_grade

    # Print Reviews snapshot
    rev = results.get("reviews", {})
    rev_lines = [
        f"Google:   {rev.get('google', {}).get('count', '-')} reviews, "
        f"{rev.get('google', {}).get('rating', '-')} stars",
        f"Facebook: {'Page found' if rev.get('facebook', {}).get('url') else 'Not found'}",
        f"Yelp:     {rev.get('yelp', {}).get('count') or '?'} reviews"
        f" {'(page found)' if rev.get('yelp', {}).get('url') else '(not found)'}",
    ]
    print_section("REVIEWS SNAPSHOT:", rev_lines)

    top_comp_reviews = (results.get("top_competitor") or {}).get("review_count") or 0
    reviews_grade = grade_reviews_cemetery(target_count, top_comp_reviews)

    grades = [
        reviews_grade,
        pack_grade,
        seo_grade,
        web_grade,
        ads_grade,
    ]
    overall = overall_grade(grades)
    results["overall_grade"] = overall
    results["all_grades"] = {
        "reviews": reviews_grade,
        "3pack": pack_grade,
        "seo": seo_grade,
        "website": web_grade,
        "ads": ads_grade,
    }

    elapsed = round(time.time() - started, 1)
    bar = "=" * 60
    print(bar)
    print(f"OVERALL GRADE: {overall}    (scan time: {elapsed}s)")
    print(bar)
    print()
    sys.stdout.flush()

    return results


def main():
    parser = argparse.ArgumentParser(description="Trade show health check - cemetery")
    parser.add_argument("business", nargs="?")
    parser.add_argument("city1", nargs="?", help="Home city")
    parser.add_argument("state", nargs="?")
    parser.add_argument("city2", nargs="?", help="Second city to scan from (optional)")
    parser.add_argument("city3", nargs="?", help="Third city to scan from (optional)")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    args = parser.parse_args()

    business = args.business
    city1 = args.city1
    state = args.state
    city2 = args.city2
    city3 = args.city3

    if not (business and city1 and state):
        print(
            "Usage: python health_check.py "
            "'Cemetery Name' 'HomeCity' 'STATE' ['SecondCity'] ['ThirdCity']"
        )
        sys.exit(1)

    cities = [city1]
    if city2 and city2.lower() not in {"skip", "none", "n/a", ""}:
        cities.append(city2)
    if city3 and city3.lower() not in {"skip", "none", "n/a", ""}:
        cities.append(city3)

    results = run_health_check(business, cities, state)

    out_json = SCRIPT_DIR / "temp_health_check.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Raw data saved: {out_json}")

    if not args.no_pdf:
        try:
            import pdf_generator
            pdf_path = pdf_generator.build_pdf(results)
            print(f"PDF generated: {pdf_path}")
        except Exception as e:
            print(f"PDF generation failed: {e}")


if __name__ == "__main__":
    main()
