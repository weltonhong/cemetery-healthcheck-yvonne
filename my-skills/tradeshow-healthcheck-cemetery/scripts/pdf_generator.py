"""
PDF Generator - Trade Show Health Check (Cemetery Edition, RRM brand)

Builds a one-page branded Ring Ring Marketing PDF scorecard for a
cemetery prospect. CTA routes to Yvonne Reese. Saves to OneDrive Desktop.
"""

import datetime
import io
import json as _json
import os
import urllib.request
from pathlib import Path

import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.utils import ImageReader


# RRM brand colors (identical to funeralhome version)
RRM_RED = colors.HexColor("#C73E3A")
RRM_DARK = colors.HexColor("#1D3557")
RRM_GRAY = colors.HexColor("#6C757D")
RRM_LIGHT = colors.HexColor("#F8EFEC")
RRM_GREEN = colors.HexColor("#2E8B57")
RRM_AMBER = colors.HexColor("#D89614")
RRM_BANNER = RRM_RED

RRM_LOGO_PATH = (
    "D:/Ring Ring Marketing/Trade Shows - General/Speaking Topics/Logos/"
    "RRM Logo/JPG/RING RING LOGO1.jpg"
)

CALENDLY_URL = (
    "https://calendly.com/yvonne-reese-ringringmarketing/"
    "yvonne-reese-marketing-audit"
)


def generate_qr_png_bytes(url):
    """Build a high-error-correction QR PNG and return its raw bytes.

    Regenerates fresh from the current CALENDLY_URL on every PDF build."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


GRADE_COLORS = {
    "A": RRM_GREEN,
    "B": RRM_GREEN,
    "C": RRM_AMBER,
    "D": RRM_RED,
    "F": RRM_RED,
}


def get_desktop_path():
    """OneDrive Desktop is the real Desktop on this machine."""
    onedrive = Path.home() / "OneDrive" / "Desktop"
    if onedrive.exists():
        return onedrive
    return Path.home() / "Desktop"


def safe_filename(name):
    keep = "-_ "
    cleaned = "".join(c if c.isalnum() or c in keep else "_" for c in name)
    return cleaned.strip().replace(" ", "_")


class CTAFooterCanvas(pdfcanvas.Canvas):
    """Custom canvas that draws a 'Call today' bar across the bottom of every
    page. On the LAST page only, also draws a QR code linking to the
    Calendly scheduling page."""

    qr_png_bytes = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for idx, page_state in enumerate(self._saved_pages):
            self.__dict__.update(page_state)
            self._draw_footer(with_qr=(idx == total - 1))
            super().showPage()
        super().save()

    def _draw_footer(self, with_qr=False):
        page_w, _ = self._pagesize
        bar_h = 1.85 * inch
        bar_y = 0.35 * inch
        margin = 0.6 * inch
        bar_w = page_w - 2 * margin

        self.setFillColor(RRM_BANNER)
        self.rect(margin, bar_y, bar_w, bar_h, fill=1, stroke=0)

        qr_size = 0.85 * inch
        qr_gap = 0.3 * inch
        qr_right_pad = 0.2 * inch
        text_left_pad = 0.25 * inch

        draw_qr = bool(with_qr and CTAFooterCanvas.qr_png_bytes)

        if draw_qr:
            text_left = margin + text_left_pad
            text_right = margin + bar_w - qr_right_pad - qr_size - qr_gap
        else:
            text_left = margin + text_left_pad
            text_right = margin + bar_w - text_left_pad

        self.setFillColor(colors.white)

        # Cemetery-specific tagline (3 lines).
        tagline = [
            ("Helvetica-Bold", 11,
             "Every week these gaps stay open, families looking for cemetery"),
            ("Helvetica-Bold", 11,
             "plots and preneed arrangements are finding your competitors instead."),
            ("Helvetica", 10,
             "We close these gaps for cemeteries across the country.  Call today."),
        ]
        contact = [
            ("Helvetica-Bold", 11.5, "Yvonne Reese, Sales Consultant"),
            ("Helvetica", 10, "Yvonne.Reese@RingRingMarketing.com"),
            ("Helvetica-Bold", 11.5, "Ring Ring Marketing  |  (888) 383-2848"),
        ]

        positions = [
            bar_y + bar_h - 20,
            bar_y + bar_h - 35,
            bar_y + bar_h - 51,
            bar_y + 52,
            bar_y + 35,
            bar_y + 18,
        ]

        all_lines = tagline + contact
        text_center_x = (text_left + text_right) / 2
        for (font, size, text), y in zip(all_lines, positions):
            self.setFont(font, size)
            if draw_qr:
                self.drawString(text_left, y, text)
            else:
                self.drawCentredString(text_center_x, y, text)

        if draw_qr:
            qr_x = margin + bar_w - qr_size - qr_right_pad
            qr_y = bar_y + bar_h - qr_size - 0.18 * inch
            try:
                img = ImageReader(io.BytesIO(CTAFooterCanvas.qr_png_bytes))
                self.drawImage(
                    img, qr_x, qr_y,
                    width=qr_size, height=qr_size, mask="auto",
                )
            except Exception:
                pass
            self.setFillColor(colors.white)
            self.setFont("Helvetica-Bold", 7.5)
            label_cx = qr_x + qr_size / 2
            self.drawCentredString(
                label_cx, qr_y - 10,
                "Scan to schedule your",
            )
            self.drawCentredString(
                label_cx, qr_y - 19,
                "free marketing audit",
            )


# ----------------------------- population lookup -----------------------------

STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}

_census_cache = {}


def _normalize_place(s):
    return s.lower().replace(".", "").replace("saint ", "st ").replace("ft ", "fort ").strip()


def get_city_population(city, state_abbr):
    """Look up city population from US Census."""
    cache_key = (city.lower().strip(), state_abbr.upper())
    if cache_key in _census_cache:
        return _census_cache[cache_key]

    fips = STATE_FIPS.get(state_abbr.upper())
    if not fips:
        return None
    url = (
        f"https://api.census.gov/data/2020/dec/pl"
        f"?get=P1_001N,NAME&for=place:*&in=state:{fips}"
    )
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        data = _json.loads(resp.read())
        city_norm = _normalize_place(city)
        matches = []
        for row in data[1:]:
            place_name = row[1].split(",")[0].strip()
            bare = _normalize_place(place_name)
            for suffix in (" city", " town", " village", " cdp", " borough", " municipality"):
                if bare.endswith(suffix):
                    bare = bare[: -len(suffix)].strip()
                    break
            if bare == city_norm:
                matches.append(int(row[0]))
        result = max(matches) if matches else None
        _census_cache[cache_key] = result
        return result
    except Exception:
        return None


def _pop_multiplier(population):
    if population is None or population < 100_000:
        return 1.0
    if population < 300_000:
        return 1.5
    if population < 750_000:
        return 2.5
    return 4.0


# ----------------------------- impact estimators -----------------------------


def estimate_lost_inquiries(results):
    """Heuristic estimate of preneed inquiries / interment inquiries per
    month going to competitors, scaled by city population.

    Cemeteries get fewer total leads than funeral homes (per-month preneed
    inquiry volume in the home city is typically 10-30 for a mid-size
    property), so we scale the base rates down a bit from the funeral
    version.
    """
    cities = results.get("cities") or []
    state = results.get("state") or ""
    pack_results = (results.get("3pack") or {}).get("results") or {}
    ads_per_bucket = results.get("ads") or {}
    bucket_labels = results.get("buckets") or list(pack_results.keys())

    low = 0.0
    high = 0.0
    for label in bucket_labels:
        if " / " in label:
            geo_city = label.split(" / ", 1)[1]
        else:
            geo_city = cities[0] if cities else ""
        pop = get_city_population(geo_city, state)
        mult = _pop_multiplier(pop)
        if not (pack_results.get(label) or {}).get("in_3_pack"):
            low += 3 * mult
            high += 7 * mult
        d = ads_per_bucket.get(label) or {}
        comps = d.get("competitors_running_ads") or []
        if comps and not d.get("prospect_running_ads"):
            low += 2 * mult
            high += 4 * mult

    target = (results.get("google_intel") or {}).get("target") or {}
    target_reviews = target.get("review_count") or 0
    top = results.get("top_competitor") or {}
    comp_reviews = top.get("review_count") or 0
    if comp_reviews >= max(20, target_reviews * 2):
        low *= 1.2
        high *= 1.2

    return int(round(low)), int(round(high))


def build_adaptive_hook(results, overall, low, high):
    """Pick the right hook copy based on the overall grade.

    D/F: aggressive lost-inquiries statement.
    B/C: 'winning in some buckets but missing others' framing.
    A:   no hook.
    """
    pack_results = (results.get("3pack") or {}).get("results") or {}
    seo = results.get("seo") or {}
    bucket_labels = results.get("buckets") or list(pack_results.keys())

    if overall in ("D", "F"):
        if high <= 0:
            return None
        return (
            f"{low}-{high} families searching for a cemetery or cemetery plot "
            f"in your service area last month found your competitors instead "
            f"of you."
        )

    if overall in ("B", "C"):
        winning = []
        losing = []
        for label in bucket_labels:
            in_pack = (pack_results.get(label) or {}).get("in_3_pack")
            seo_rank = (seo.get(label) or {}).get("rank")
            in_seo = seo_rank is not None and seo_rank <= 10
            if in_pack or in_seo:
                winning.append(label)
            else:
                losing.append(label)

        if winning and losing:
            win_lab = winning[0]
            if len(losing) == 1:
                lose_str = losing[0]
            elif len(losing) == 2:
                lose_str = f"{losing[0]} and {losing[1]}"
            else:
                lose_str = ", ".join(losing[:-1]) + f", and {losing[-1]}"
            return (
                f"You're winning in {win_lab}. But families searching in "
                f"{lose_str} are finding your competitors because they can't "
                f"find you there."
            )
        if high > 0:
            return (
                f"{low}-{high} families slipped through to your competitors "
                f"last month. The gaps are fixable."
            )
        return None

    return None


def count_competing_cemeteries(results):
    """Count unique cemeteries that appeared anywhere in the scan."""
    seen = set()
    pack_results = (results.get("3pack") or {}).get("results") or {}
    ads_per_bucket = results.get("ads") or {}
    bucket_labels = results.get("buckets") or list(pack_results.keys())

    def norm(name):
        if not name:
            return ""
        return " ".join(name.lower().strip().split())

    for label in bucket_labels:
        for name in (pack_results.get(label) or {}).get("top_3", []) or []:
            key = norm(name)
            if key:
                seen.add(key)
        for name in (ads_per_bucket.get(label) or {}).get("all_advertisers", []) or []:
            key = norm(name)
            if key:
                seen.add(key)

    intel_comps = (results.get("google_intel") or {}).get("competitors") or []
    for c in intel_comps:
        key = norm(c.get("name") or "")
        if key:
            seen.add(key)

    return len(seen)


def build_recommendations(results):
    """Top-2 'Where Your Inquiries Are Going' bullets, cemetery voice."""
    return _build_recommendations_top2(results)


def _build_recommendations_top2(results):
    pack_results = (results.get("3pack") or {}).get("results") or {}
    seo = results.get("seo") or {}
    ads_per_bucket = results.get("ads") or {}
    target = (results.get("google_intel") or {}).get("target") or {}
    top = results.get("top_competitor") or {}
    web = results.get("website") or {}
    bucket_labels = results.get("buckets") or list(pack_results.keys())

    candidates = []

    # ----- 3-Pack: name the cemeteries that own the map ------------------
    missing_packs = [
        b for b in bucket_labels
        if not (pack_results.get(b) or {}).get("in_3_pack")
    ]
    if missing_packs:
        target_bucket = missing_packs[0]
        d = pack_results.get(target_bucket) or {}
        top_3 = [t for t in (d.get("top_3") or []) if t][:3]
        if top_3:
            comps = ", ".join(top_3)
            score = 100 + len(missing_packs) * 8
            candidates.append((score,
                f"<b>{comps}</b> own the Google Map Pack for \"{target_bucket}\". "
                f"When a family searches that, those cemeteries get the inquiry. "
                f"Your name never appears on the map. Every search is a family "
                f"ready to buy a plot or arrange interment this month, calling "
                f"your competitor instead of you."
            ))

    # ----- Reviews: name the competitor and the gap ---------------------
    rc = target.get("review_count") or 0
    comp_rc = top.get("review_count") or 0
    if comp_rc > 0 and (comp_rc - rc) >= 5:
        comp_name = top.get("name", "your top competitor")
        score = min(99, (comp_rc - rc) * 2)
        candidates.append((score,
            f"You have <b>{rc}</b> Google reviews. {comp_name} has <b>{comp_rc}</b>. "
            f"When a family is choosing where to bury a loved one, they look at "
            f"proof. Every review gap is a preneed family or an at-need interment "
            f"going to your competitor."
        ))

    # ----- Ads: cemetery-vertical framing -------------------------------
    # If competitors ARE running ads and prospect is not -> standard pain.
    # If NO ONE is running ads in a bucket -> "open lane" opportunity.
    chose_ads_candidate = False
    for label in bucket_labels:
        d = ads_per_bucket.get(label) or {}
        if d.get("prospect_running_ads"):
            continue
        comps = d.get("competitors_running_ads") or []
        all_ads = d.get("all_advertisers") or []
        if comps or len(all_ads) >= 2:
            display_names = [c["name"] for c in comps[:3]] if comps else all_ads[:3]
            names = ", ".join(display_names)
            score = 75 + len(all_ads) * 3
            candidates.append((score,
                f"<b>{names}</b> are paying Google to put their phone number "
                f"above everything else when families search \"{label}\". You "
                f"are not in that auction. Every click on a sponsored result is "
                f"a family handing their preneed inquiry to your competitor "
                f"before they ever see your name."
            ))
            chose_ads_candidate = True
            break

    # If no bucket had a competitor advertiser at all, recommend grabbing
    # the open lane in the home city.
    if not chose_ads_candidate:
        empty_buckets = [
            b for b in bucket_labels
            if not (ads_per_bucket.get(b) or {}).get("all_advertisers")
        ]
        if empty_buckets:
            target_bucket = empty_buckets[0]
            score = 65
            candidates.append((score,
                f"No cemetery is running Google Ads for \"{target_bucket}\". "
                f"This is an open lane. The first cemetery to start advertising "
                f"will capture the high-intent preneed searches with no "
                f"competition for the click -- and the preneed sales that "
                f"come with them."
            ))

    # ----- SEO Organic --------------------------------------------------
    not_ranking = [
        b for b in bucket_labels
        if (seo.get(b) or {}).get("rank") is None
        or ((seo.get(b) or {}).get("rank") or 99) > 10
    ]
    if not_ranking:
        labels_str = ", ".join(not_ranking)
        score = 50 + len(not_ranking) * 5
        candidates.append((score,
            f"Families searching \"{labels_str}\" scroll the regular Google "
            f"results and your cemetery is not on the first page. The 'cemetery "
            f"plots' searcher is a preneed buyer with intent to purchase. Every "
            f"researcher who never finds you is a preneed sale going to whoever "
            f"does show up."
        ))

    # ----- Website: cemetery-specific painful failures ------------------
    web_checks = web.get("checks") or {}
    psi = web.get("pagespeed_score")
    if psi is not None and psi < 40:
        score = 70
        candidates.append((score,
            f"Your homepage scores <b>{psi}/100</b> on mobile speed. Families "
            f"researching cemeteries on iPhones wait five-plus seconds before "
            f"they see anything and most of them bounce before the page loads. "
            f"Every bounce is a preneed inquiry you should have answered that "
            f"you never will."
        ))
    elif web_checks.get("property_tour_photos") is False:
        score = 65
        candidates.append((score,
            f"Your website does not show actual property photos -- gallery, "
            f"aerial, or sections. Cemeteries are a buying-on-sight business; "
            f"families want to SEE the grounds before they call. When the photos "
            f"are stock or sparse, families call the cemetery whose property they "
            f"can already picture themselves at."
        ))
    elif web_checks.get("preneed_form") is False:
        score = 60
        candidates.append((score,
            f"Your website has no clear preneed contact form or 'schedule a "
            f"property tour' CTA. Preneed shoppers will not pick up the phone "
            f"on the first visit -- they want to fill out a form and have "
            f"someone call them back. Without that, you lose them to the "
            f"cemetery whose form is one click away."
        ))
    elif web_checks.get("inventory_info") is False:
        score = 55
        candidates.append((score,
            f"Your website is vague about what you actually offer -- plots, "
            f"mausoleum crypts, columbarium niches, cremation gardens, green "
            f"burial. When families can't see what is available, they assume "
            f"you don't have it and call the cemetery whose website spells it "
            f"out. Vague offerings cost preneed sales."
        ))
    elif web_checks.get("google_reviews_widget") is False and rc >= 20:
        score = 45
        candidates.append((score,
            f"Your <b>{rc}</b> Google reviews are nowhere on your homepage. "
            f"The proof you already earned is invisible to every family who "
            f"lands there, so they bounce to the cemetery whose reviews are "
            f"right on the screen."
        ))

    candidates.sort(key=lambda x: -x[0])
    if candidates:
        return [text for _, text in candidates[:2]]

    return [
        "Your foundation is strong across reviews, local visibility, and your "
        "website. The cemeteries in your service area are watching for any "
        "opening. Stay ahead by compounding what is already working before "
        "they catch up."
    ]


def build_pdf(results):
    business = results.get("business", "Prospect")
    city = results.get("city", "")
    state = results.get("state", "")
    overall = results.get("overall_grade", "F")
    grades = results.get("all_grades", {})

    today = datetime.date.today().strftime("%B %d, %Y")
    desktop = get_desktop_path()
    desktop.mkdir(parents=True, exist_ok=True)
    fname = f"HealthCheck_{safe_filename(business)}_{datetime.date.today().isoformat()}.pdf"
    out_path = desktop / fname

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=2.35 * inch,
        title=f"Online Health Check - {business}",
        author="Ring Ring Marketing",
    )

    styles = getSampleStyleSheet()
    h_brand = ParagraphStyle(
        "brand", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=18, textColor=RRM_RED,
        spaceAfter=2,
    )
    h_sub = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=RRM_GRAY,
        spaceAfter=10,
    )
    h_title = ParagraphStyle(
        "title", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=16, textColor=RRM_DARK,
        spaceAfter=2,
    )
    h_meta = ParagraphStyle(
        "meta", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, textColor=RRM_GRAY,
        spaceAfter=10,
    )
    h_section = ParagraphStyle(
        "section", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=12, textColor=RRM_DARK,
        spaceAfter=6, spaceBefore=4,
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"],
        fontName="Helvetica", fontSize=11, textColor=colors.black,
        leading=14, spaceAfter=6,
    )
    rec_style = ParagraphStyle(
        "rec", parent=body, leftIndent=10, bulletIndent=0, spaceAfter=8,
    )

    story = []

    if os.path.exists(RRM_LOGO_PATH):
        try:
            reader = ImageReader(RRM_LOGO_PATH)
            iw, ih = reader.getSize()
            target_w = 2.5 * inch
            target_h = target_w * (ih / iw)
            logo = Image(RRM_LOGO_PATH, width=target_w, height=target_h)
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 6))
        except Exception:
            pass

    story.append(Paragraph(f"Online Health Check: {business}", h_title))
    story.append(Paragraph(
        f"{city}, {state}  |  Scanned {today}",
        h_meta,
    ))

    low, high = estimate_lost_inquiries(results)
    hook_text = build_adaptive_hook(results, overall, low, high)
    hook_style = ParagraphStyle(
        "hook", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=15, textColor=RRM_RED,
        leading=19, alignment=1, spaceAfter=8, spaceBefore=4,
    )
    if hook_text:
        story.append(Paragraph(hook_text, hook_style))

    competitor_count = count_competing_cemeteries(results)
    snapshot_style = ParagraphStyle(
        "snapshot", parent=styles["Normal"],
        fontName="Helvetica", fontSize=11, textColor=RRM_DARK,
        leading=14, spaceAfter=10, alignment=1,
    )
    if competitor_count > 0:
        story.append(Paragraph(
            f"There are <b>{competitor_count}</b> cemeteries competing for "
            f"those families in your service area right now.",
            snapshot_style,
        ))
    elif results.get("limited_competition"):
        story.append(Paragraph(
            f"Limited competition in {city} -- few or no other cemeteries "
            f"surface in the local search results. That is an asset to defend.",
            snapshot_style,
        ))

    overall_color = GRADE_COLORS.get(overall, RRM_GRAY)
    banner_label_style = ParagraphStyle(
        "bannerLabel", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=12, textColor=colors.white,
        alignment=1, leading=14, spaceAfter=2,
    )
    banner_letter_style = ParagraphStyle(
        "bannerLetter", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=36, textColor=colors.white,
        alignment=1, leading=38,
    )
    overall_table = Table(
        [[[
            Paragraph("OVERALL GRADE", banner_label_style),
            Paragraph(overall, banner_letter_style),
        ]]],
        colWidths=[7.0 * inch],
    )
    overall_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), overall_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(overall_table)
    story.append(Spacer(1, 12))

    target = (results.get("google_intel") or {}).get("target") or {}
    pack = results.get("3pack") or {}
    seo = results.get("seo") or {}
    web = results.get("website") or {}
    ads = results.get("ads") or {}
    bucket_labels = results.get("buckets") or []

    rc = target.get("review_count")
    rating = target.get("rating")
    maps_url = target.get("maps_url") or ""
    reviews_detail = (
        f"<b>{rc if rc is not None else '-'}</b> reviews, "
        f"<b>{rating if rating is not None else '-'}</b> stars"
    )
    if maps_url:
        reviews_detail += (
            f'  <a href="{maps_url}" color="#C73E3A">'
            f'<u>View Reviews</u></a>'
        )

    intel_comps = (results.get("google_intel") or {}).get("competitors") or []

    def _is_self(name):
        if not name or not business:
            return False
        return (business.lower() in name.lower()
                or name.lower() in business.lower())

    filtered_comps = [
        c for c in intel_comps
        if c.get("name") and not _is_self(c.get("name", ""))
    ]
    top_3_comps = sorted(
        filtered_comps,
        key=lambda c: c.get("review_count") or 0,
        reverse=True,
    )[:3]
    if top_3_comps:
        comp_strs = []
        for c in top_3_comps:
            name = c.get("name", "?")
            count = c.get("review_count") or 0
            crating = c.get("rating")
            if crating is not None:
                comp_strs.append(
                    f"{name} ({count} reviews, {crating} stars)"
                )
            else:
                comp_strs.append(f"{name} ({count} reviews)")
        reviews_detail += "<br/><b>Competitors:</b> " + ", ".join(comp_strs)
    elif results.get("limited_competition"):
        reviews_detail += "<br/><b>Limited competition</b> in this market."

    pack_results = pack.get("results") or {}

    def pack_status(d):
        if not d or "error" in d:
            return "ERROR"
        top_3 = d.get("top_3") or []
        if not top_3:
            return "No local map pack found for this bucket"
        top_3_str = ", ".join(top_3[:3])
        if d.get("in_3_pack"):
            return f"FOUND rank {d.get('rank')} (Top 3: {top_3_str})"
        return f"NOT FOUND (Top 3: {top_3_str})"

    pack_lines_html = [
        f"<b>{label}:</b> {pack_status(pack_results.get(label))}"
        for label in bucket_labels
    ]
    pack_detail = "<br/>".join(pack_lines_html) or "No data"

    import re as _re
    def trim_title(t):
        t = (t or "").replace("&amp;", "&").replace("&#39;", "'") \
                     .replace("&quot;", '"').replace("&#x27;", "'")
        short = _re.split(
            r"\s+[\|•:]\s+|\s+-\s+|\s+–\s+", t, maxsplit=1
        )[0].strip()
        return (short or t)[:60]

    seo_lines_html = []
    for label in bucket_labels:
        d = seo.get(label) or {}
        rank = d.get("rank")
        top_3 = d.get("top_3") or []
        cleaned = [trim_title(t) for t in top_3[:3] if t]
        if not cleaned:
            seo_lines_html.append(
                f"<b>{label}:</b> No organic results found for this bucket"
            )
            continue
        top_3_str = ", ".join(cleaned)
        if rank is None:
            seo_lines_html.append(
                f"<b>{label}:</b> Not in top 10 (Top 3: {top_3_str})"
            )
        else:
            seo_lines_html.append(
                f"<b>{label}:</b> Rank {rank} (Top 3: {top_3_str})"
            )
    seo_detail = "<br/>".join(seo_lines_html) if seo_lines_html else "No data"

    if web.get("unverified"):
        reason = web.get("unverified_reason") or web.get("error") or "blocked"
        web_detail = f"Unable to verify -- {reason}"
        web_grade_display = "N/A"
    else:
        wc = web.get("checks", {})
        psi_score = web.get("pagespeed_score")
        platform = web.get("platform") or "Unknown"
        property_map = web.get("property_map")
        inv_offerings = (web.get("inventory_offerings") or [])[:5]
        bits = []
        bits.append("Real photos: " + ("Yes" if wc.get("real_photos") else "No (stock)"))
        if psi_score is not None:
            bits.append(f"PageSpeed: {psi_score}/100")
        else:
            bits.append("PageSpeed: ?")
        bits.append("Family/owner story: " + ("Yes" if wc.get("family_owner_story") else "No"))
        bits.append("Preneed form: " + ("Yes" if wc.get("preneed_form") else "No"))
        bits.append("Schema: " + ("Yes" if wc.get("localbusiness_schema") else "No"))
        bits.append("Reviews widget: " + ("Yes" if wc.get("google_reviews_widget") else "No"))
        bits.append("Property tour: " + ("Yes" if wc.get("property_tour_photos") else "No"))
        if wc.get("inventory_info"):
            inv_label = "Yes"
            if inv_offerings:
                inv_label = f"Yes ({', '.join(inv_offerings)})"
            bits.append("Inventory: " + inv_label)
        else:
            bits.append("Inventory: No")
        web_detail = "  |  ".join(bits)
        extras = []
        if property_map is not None:
            extras.append(f"<b>Property map:</b> {'Yes' if property_map else 'No'}")
        if platform and platform != "Unknown":
            extras.append(f"<b>Platform:</b> {platform}")
        if extras:
            web_detail += "<br/>" + "  |  ".join(extras)
        web_grade_display = grades.get("website") or "F"

    # Ads per bucket - cemetery framing for empty buckets
    ads_lines = []
    business_running_anywhere = False
    for label in bucket_labels:
        d = ads.get(label) or {}
        if d.get("prospect_running_ads"):
            business_running_anywhere = True
        advs = (d.get("all_advertisers") or [])[:3]
        if advs:
            ads_lines.append(f"<b>{label}:</b> {', '.join(advs)}")
        else:
            ads_lines.append(f"<b>{label}:</b> No ads detected (open lane)")
    ads_lines.append(
        f"<b>{business}:</b> "
        + ("Running" if business_running_anywhere else "Not running")
    )
    ads_detail = "<br/>".join(ads_lines) or "No data"

    cell_style = ParagraphStyle(
        "cell", parent=styles["Normal"],
        fontName="Helvetica", fontSize=11, leading=13,
        textColor=colors.black,
    )
    area_style = ParagraphStyle(
        "area", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=12, leading=14,
        textColor=colors.black,
    )

    def cell(text):
        return Paragraph(text, cell_style)

    def area(text):
        return Paragraph(text, area_style)

    rows = [
        ["AREA", "GRADE", "DETAILS"],
        [area("Google Reviews"), grades.get("reviews", "F"), cell(reviews_detail)],
        [area("Google Local Map Rankings"), grades.get("3pack", "F"), cell(pack_detail)],
        [area("Google Organic Rankings (SEO)"), grades.get("seo", "F"), cell(seo_detail)],
        [area("Google Ads"), grades.get("ads", "F"), cell(ads_detail)],
        [area("Website"), web_grade_display, cell(web_detail)],
    ]

    sc = Table(
        rows,
        colWidths=[2.0 * inch, 0.7 * inch, 4.3 * inch],
    )
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), RRM_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 1), (1, -1), 12),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, RRM_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for i, row in enumerate(rows[1:], start=1):
        g = row[1]
        style.append(("TEXTCOLOR", (1, i), (1, i), GRADE_COLORS.get(g, RRM_GRAY)))
    sc.setStyle(TableStyle(style))
    story.append(sc)
    story.append(Spacer(1, 14))

    story.append(Paragraph("WHERE YOUR INQUIRIES ARE GOING", h_section))
    for rec in build_recommendations(results):
        story.append(Paragraph(f"&bull; {rec}", rec_style))
    story.append(Spacer(1, 10))

    try:
        CTAFooterCanvas.qr_png_bytes = generate_qr_png_bytes(CALENDLY_URL)
    except Exception as e:
        print(f"QR generation failed: {e}")
        CTAFooterCanvas.qr_png_bytes = None

    doc.build(story, canvasmaker=CTAFooterCanvas)
    return str(out_path)


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_generator.py <results.json>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    print(build_pdf(data))
