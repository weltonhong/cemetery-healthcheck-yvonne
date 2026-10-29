"""
PDF Generator - Trade Show Health Check (Cemetery Edition, RRM brand)

Builds a one-page branded Ring Ring Marketing PDF scorecard for a
cemetery prospect. CTA routes to Yvonne Reese. Saves to OneDrive Desktop.
"""

import datetime
import io
import os

from pathlib import Path

import headline
import listing_confirm
import ads_words
import ads_records
from xml.sax.saxutils import escape
import measured

import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
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

# Rep block printed on every page of the CTA footer. BRAND_LINE differs
# between SCMM ("Senior Care Marketing Max") and RRM ("Ring Ring
# Marketing") deploys so the cemetery RRM repo uses this block.
REP_NAME = "Yvonne Reese"
REP_EMAIL = "Yvonne.Reese@RingRingMarketing.com"
BRAND_LINE = "Ring Ring Marketing  |  (888) 383-2848"


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
             "We close these gaps for cemeteries like yours.  Call today."),
        ]
        contact = [
            ("Helvetica-Bold", 11.5, f"{REP_NAME}, Sales Consultant"),
            ("Helvetica", 10, REP_EMAIL),
            ("Helvetica-Bold", 11.5, BRAND_LINE),
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
        if not getattr(CTAFooterCanvas, "gaps_measured", True):
            # "Every week these gaps stay open" only beside a gap the sheet measured (Welton 2026-10-21).
            all_lines = [(f, z, "") for f, z, _ in tagline[:2]] + all_lines[2:]
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


# ----------------------------- impact estimators -----------------------------


# Map-pack rows carry THREE states, not two, and the difference decides
# whether anything may be said about the prospect.
#
#   UNSCANNED          the fetch failed. Neither a finding nor a non-finding.
#   NO_PACK            Google served no local pack for that search at all.
#                      There is nothing to be absent from, so it is not a gap
#                      and no competitor "owns the map" there.
#   IN_PACK            the prospect is in it.
#   ABSENT_FROM_PACK   a pack exists and the prospect is not in it. The only
#                      one of the four that is a finding about the prospect.
#
# `in_3_pack` alone cannot tell NO_PACK from ABSENT_FROM_PACK: it is False for
# both. Every selector below keys on this function instead.
UNSCANNED = "UNSCANNED"
NO_PACK = "NO_PACK"
IN_PACK = "IN_PACK"
ABSENT_FROM_PACK = "ABSENT_FROM_PACK"
UNCONFIRMED = "UNCONFIRMED"


def pack_status(pack_row):
    """Which of the four states this map-pack row is in."""
    row = pack_row or {}
    if row.get("error"):
        return UNSCANNED
    if row.get("in_3_pack"):
        return IN_PACK
    if row.get("maybe_rank") or row.get("no_id"):
        # A card may be theirs but its place id did not confirm it
        # (scripts/map_identity.py): never a rank, never a miss.
        return UNCONFIRMED
    if not [t for t in (row.get("top_3") or []) if t]:
        # No pack was served. Measured 2026-08-20 across 27 real
        # vertical/market queries: a genuinely packless search did not occur
        # once, so this state is almost always a measurement problem rather
        # than a fact about the market. Either way it is not a gap.
        return NO_PACK
    return ABSENT_FROM_PACK


def build_recommendations(results):
    """Top-2 'Where Your Inquiries Are Going' bullets, cemetery voice."""
    return _build_recommendations_top2(results)


def _typed(bucket, seo, results):
    """The words a person types for a search, as the scan sent them ("funeral home Lancaster NY"), never the sheet's
    internal label "funeral home / Lancaster" (Welton 2026-10-22)."""
    q = (seo.get(bucket) or {}).get("query")
    if q:
        return q
    kw, _, city = bucket.partition(" / ")
    return " ".join(x for x in (kw, city, results.get("state") or "") if x)


def _quoted(searches):
    q = ['"%s"' % s for s in searches]
    return q[0] if len(q) == 1 else ", ".join(q[:-1]) + " and " + q[-1]


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
    # Unscanned buckets excluded: naming a competitor as owning the map for a
    # search whose SERP never came back is a fabricated finding, and it also
    # inflates the score below.
    # ABSENT_FROM_PACK only, which means every entry is guaranteed to
    # have a top_3 to name. The old list also admitted rows where no
    # pack existed; because the consumer below took [0] and gave up if
    # it had no top_3, a single packless home city SUPPRESSED the whole
    # bullet -- and with it two genuine, nameable gaps in other cities.
    # Both points named; who Google shows, never what a family then does (Welton 2026-10-22).
    # A listing Google marks closed has no map position to report (measured.listing_closed, Welton 2026-10-28).
    mb = None if measured.listing_closed(results) else measured.map_bullet([(k, pack_results.get(k), (pack_results.get(k) or {}).get("door"),
                               _typed(k, seo, results)) for k in bucket_labels], 'Families')
    if mb:
        candidates.append(mb)

    # ----- Reviews: name the competitor and the gap ---------------------
    rc = target.get("review_count") or 0
    comp_rc = top.get("review_count") or 0
    if listing_confirm.known(target) and not measured.listing_closed(results) and comp_rc > 0 and (comp_rc - rc) >= 5:
        comp_name = top.get("name", "your top competitor")
        score = min(99, (comp_rc - rc) * 2)
        candidates.append((score,
            f"You have <b>{rc}</b> Google {measured.reviews_word(rc)}. {comp_name} has <b>{comp_rc}</b>. "
            f"When a family is choosing where to bury a loved one, they look at "
            f"proof."
        ))

    # Ads are off the sheet (Welton 2026-10-22): no ads bullet and no "open lane".
    # No organic bullet (Welton 2026-10-29): "not on the first page of the regular results" was this route's
    # page-one miss, which agreed with a live browser 14 of 27 times (receipt 20261029T035000_route-vs-browser-measure).

    # ----- Website: cemetery-specific painful failures ------------------
    web_checks = web.get("checks") or {}
    psi = web.get("pagespeed_score")
    if psi is not None and psi < 40:
        score = 70
        candidates.append((score,
            f"Google's mobile speed test scored your homepage <b>{measured.speed_text(web)} out of 100</b>. Families "
            f"researching cemeteries on iPhones are left waiting on a page Google scores as slow, and a slow page loses them before it loads. "
            f""
        ))
    elif web_checks.get("property_tour_photos") is False:
        score = 65
        candidates.append((score,
            f"Your website does not show actual property photos: gallery, "
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
            f"on the first visit. They want to fill out a form and have "
            f"someone call them back. Without that, you lose them to the "
            f"cemetery whose form is one click away."
        ))
    elif web_checks.get("inventory_info") is False:
        score = 55
        candidates.append((score,
            f"Your website is vague about what you actually offer: plots, "
            f"mausoleum crypts, columbarium niches, cremation gardens, green "
            f"burial. When families can't see what is available, they assume "
            f"you don't have it and call the cemetery whose website spells it "
            f"out. Vague offerings cost preneed sales."
        ))
    elif web_checks.get("google_reviews_widget") is False and rc >= 20:
        score = 45
        candidates.append((score,
            f"Your <b>{rc}</b> Google {measured.reviews_word(rc)} {'is' if measured.reviews_word(rc) == 'review' else 'are'} nowhere on your homepage. "
            f"The proof you already earned is invisible to every family who "
            f"lands there, so they bounce to the cemetery whose reviews are "
            f"right on the screen."
        ))

    candidates.sort(key=lambda x: -x[0])
    if candidates:
        return [text for _, text in candidates[:2]]

    # A sentence about everything needs everything measured; otherwise nothing prints
    # (scripts/measured.py, Welton 2026-10-21).
    if not measured.everything_read(results, bucket_labels, listing_confirm.known(target) and not measured.listing_closed(results), website_needed=True):
        return []
    return [
        "Your foundation is strong across reviews, local visibility, and your "
        "website. The cemeteries in your service area are watching for any "
        "opening. Stay ahead by compounding what is already working before "
        "they catch up."
    ]


def _web_answer(value, no_text):
    """Yes / the No text / "Couldn't check" (None: the page the check needed could not be read)."""
    if value is None:
        return "Couldn't check"
    return "Yes" if value else no_text


def build_pdf(results):
    business = results.get("business", "Prospect")
    city = results.get("city", "")
    state = results.get("state", "")
    overall = measured.grade_text(results.get("overall_grade"))
    grades = results.get("all_grades", {})

    today = measured.sheet_date_text(results)   # the rep's day, never the server's UTC day
    desktop = get_desktop_path()
    desktop.mkdir(parents=True, exist_ok=True)
    fname = f"HealthCheck_{safe_filename(business)}_{measured.sheet_day(results)[0] or 'undated'}.pdf"
    out_path = desktop / fname

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=2.2 * inch,  # 1.85in CTA footer + 0.35in gap (2.35 until 2026-10-22: one-page sheets spilled)
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
        keepWithNext=1,  # never left alone at the foot of a page (Welton 2026-10-22: Haven, Home Instead)
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"],
        fontName="Helvetica", fontSize=11, textColor=colors.black,
        leading=14, spaceAfter=6,
    )
    rec_style = ParagraphStyle(
        "rec", parent=body, leftIndent=10, bulletIndent=0, spaceAfter=8, allowWidows=0,
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
        f"{city}, {state}" + (f"  |  Scanned {today}" if today else ""),
        h_meta,
    ))

    # THE HOOK: only what the scan measured (scripts/headline.py; Welton
    # 2026-10-20 dropped the lost-calls estimate, which was not measured).
    hook_text = headline.measured_headline(results, 'Families')
    hook_style = ParagraphStyle(
        "hook", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=15, textColor=RRM_RED,
        leading=19, alignment=1, spaceAfter=8, spaceBefore=4,
    )
    if hook_text:
        story.append(Paragraph(hook_text, hook_style))

    # No "There are N ... competing" line (Welton 2026-10-20): the count merged map,
    # ads and Google lists, counted one business spelled two ways twice, and
    # nothing on the sheet showed where it came from (10 on La Paloma's NY run, 11 on NV).
    # The "Limited competition ... an asset to defend" line went with it: it printed
    # whenever the competitor list was empty, including when the lookup failed.

    overall_color = GRADE_COLORS.get(None if measured.listing_closed(results) else overall, RRM_GRAY)
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
    # No letter for a listing Google marks closed: the sentence says why (Welton 2026-10-28).
    banner_closed_style = ParagraphStyle(
        "bannerClosed", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=13, textColor=colors.white,
        alignment=1, leading=16,
    )
    overall_table = Table(
        [[[
            Paragraph("OVERALL GRADE", banner_label_style),
            Paragraph(overall, banner_letter_style) if not measured.listing_closed(results) else Paragraph(
                escape(measured.closed_overall(measured.listing_closed(results))), banner_closed_style),
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
    story.append(Spacer(1, 6))

    target = (results.get("google_intel") or {}).get("target") or {}
    pack = results.get("3pack") or {}
    seo = results.get("seo") or {}
    web = results.get("website") or {}
    ads = results.get("ads") or {}
    bucket_labels = results.get("buckets") or []

    # Google marks their listing closed: said in Google's words, reviews and map not graded (Welton 2026-10-28).
    closed_listing = measured.listing_closed(results)
    rc = target.get("review_count")
    rating = target.get("rating")
    maps_url = target.get("maps_url") or ""
    reviews_detail = (
        f"<b>{rc if rc is not None else 0}</b> {measured.reviews_word(rc if rc is not None else 0)}, "
        f"<b>{rating if rating is not None else '-'}</b> stars"
    ) if listing_confirm.known(target) and not closed_listing else (
        escape(measured.closed_reviews_detail(target, closed_listing)) if closed_listing
        else listing_confirm.reason(target))
    if maps_url:
        reviews_detail += (
            f'  <a href="{maps_url}" color="#C73E3A">'
            f'<u>View Reviews</u></a>'
        )

    intel_comps = measured.open_rivals((results.get("google_intel") or {}).get("competitors"))

    def _is_self(name):
        if not name or not business:
            return False
        return (business.lower() in name.lower()
                or name.lower() in business.lower())

    filtered_comps = [
        c for c in intel_comps
        if c.get("name") and not measured.same_listing(c, (results.get("google_intel") or {}).get("target"), business)
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
                    f"{name} ({count} {measured.reviews_word(count)}, {crating} stars)"
                )
            else:
                comp_strs.append(f"{name} ({count} {measured.reviews_word(count)})")
        reviews_detail += "<br/><b>Competitors:</b> " + ", ".join(comp_strs)
    # No "Limited competition in this market" (Welton 2026-10-20): it printed when
    # the competitor list was empty, which is also what a failed lookup returns.

    pack_results = pack.get("results") or {}

    def pack_cell(d):
        """The display string for one map-pack row.

        NOT the module-level pack_status, which returns a STATE. Two
        functions of one name in one file, returning different kinds of
        thing, is a trap for the next reader; this one is the renderer.
        """
        if not d or "error" in d:
            return "Couldn't check this search"
        top_3 = d.get("top_3") or []
        if not top_3:
            if d.get("confirmed_empty"):
                return "Google shows no map pack for this search"
            # Not confirmed. Deliberately says nothing about the prospect:
            # a rep reads this row out loud to them.
            return "Map results unconfirmed for this search"
        top_3_str = ", ".join(top_3[:3])
        if d.get("in_3_pack"):
            return f"FOUND rank {d.get('rank')} (Top 3: {top_3_str})"
        if d.get("maybe_rank"):
            return f"Couldn't confirm: #{d.get('maybe_rank')} may be you (Top 3: {top_3_str})"
        if d.get("no_id"):
            return f"Couldn't confirm which card is theirs (Top 3: {top_3_str})"
        return f"NOT FOUND (Top 3: {top_3_str})"

    pack_lines_html = [
        f"<b>{label}:</b> " + escape(measured.closed_map_line(pack_results.get(label), (pack_results.get(label) or {}).get("door"), measured.town_of(label), closed_listing) if closed_listing else measured.map_line(pack_results.get(label), (pack_results.get(label) or {}).get("door"), measured.town_of(label)))
        for label in bucket_labels
    ]
    pack_lines_html += [n for n in [measured.office_note([(pack_results.get(k) or {}).get("door") for k in bucket_labels])] if n]
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
        if measured.organic_failed(d):
            # The prospect is handed this PDF. A failed fetch must not appear
            # on it as a finding about their rankings.
            seo_lines_html.append(
                f"<b>{label}:</b> " + escape(measured.organic_line(d, d.get("door"), measured.town_of(label))))
            continue
        top_3_str = ", ".join(cleaned)
        # No names to list is not "no organic results" (Welton 2026-10-20): the page was read and the
        # rank stands; scripts/organic_names.py only names real businesses, so the list can be empty.
        top_3_part = f" (Top 3: {top_3_str})" if cleaned else ""
        seo_lines_html.append(f"<b>{label}:</b> " + escape(measured.organic_line(d, d.get("door"), measured.town_of(label))))
    seo_lines_html += [n for n in [measured.office_note([(seo.get(k) or {}).get("door") for k in bucket_labels])] if n]
    seo_detail = "<br/>".join(seo_lines_html) if seo_lines_html else "No data"
    # Beside rows that were read, the blank grade is explained in Welton's words (2026-10-24), never a bare N/A.
    seo_not_graded = measured.seo_not_graded(results, grades.get("seo"))
    if seo_not_graded:
        seo_detail = '<font size="8"><i>%s</i></font><br/>%s' % (escape(measured.SEO_NOT_GRADED), seo_detail)

    if web.get("unverified"):
        reason = web.get("unverified_reason") or web.get("error") or "blocked"
        web_detail = reason if reason.startswith("Couldn't check") else f"Couldn't check: {reason}"
        web_grade_display = "N/A"
    else:
        wc = web.get("checks", {})
        psi_score = web.get("pagespeed_score")
        platform = web.get("platform") or "Unknown"
        property_map = web.get("property_map")
        inv_offerings = (web.get("inventory_offerings") or [])[:5]
        bits = []
        bits.append("Real photos: " + _web_answer(wc.get("real_photos"), "No (stock)"))
        if psi_score is not None:
            bits.append(f"PageSpeed: {measured.speed_text(web)}/100"
                        + (f" ({len(web['pagespeed_runs'])} tests today)" if web.get("pagespeed_runs") else ""))
        else:
            bits.append("PageSpeed: Couldn't check")
        bits.append("Family/owner story: " + _web_answer(wc.get("family_owner_story"), "No"))
        bits.append("Preneed form: " + _web_answer(wc.get("preneed_form"), "No"))
        bits.append("Schema: " + _web_answer(wc.get("localbusiness_schema"), "No"))
        bits.append("Reviews widget: " + _web_answer(wc.get("google_reviews_widget"), "No"))
        bits.append("Property tour: " + _web_answer(wc.get("property_tour_photos"), "No"))
        if wc.get("inventory_info"):
            inv_label = "Yes"
            if inv_offerings:
                inv_label = f"Yes ({', '.join(inv_offerings)})"
            bits.append("Inventory: " + inv_label)
        else:
            bits.append("Inventory: " + _web_answer(wc.get("inventory_info"), "No"))
        web_detail = "  |  ".join(bits)
        extras = []
        if property_map is not None:
            extras.append(f"<b>Property map:</b> {'Yes' if property_map else 'No'}")
        if platform and platform != "Unknown":
            extras.append(f"<b>Platform:</b> {platform}")
        if extras:
            web_detail += "<br/>" + "  |  ".join(extras)
        web_grade_display = grades.get("website") or "N/A"


    cell_style = ParagraphStyle(
        "cell", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, leading=12,
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

    if closed_listing:
        note = '<font size="8"><i>%s</i></font><br/>' % escape(measured.closed_not_graded(closed_listing))
        reviews_detail, pack_detail = note + reviews_detail, note + pack_detail
    rows = [
        ["AREA", "GRADE", "DETAILS"],
        [area("Google Reviews"), "" if closed_listing else grades.get("reviews") or "N/A", cell(reviews_detail)],
        [area("Google Local Map Rankings"), "" if closed_listing else measured.grade_text(grades.get("3pack")),
         cell(pack_detail)],
        [area("Google Organic Rankings (SEO)"), "" if seo_not_graded else measured.grade_text(grades.get("seo")),
         cell(seo_detail)],
        [area("Website"), web_grade_display, cell(web_detail)],
    ]

    # One table row per search line, so a tall section breaks between two searches and the table never breaks
    # after its first row (Welton 2026-10-22: Pacer's page 1 held only Google Reviews, the map row moved whole to
    # page 2). The lines of one section share its background and have no rule between them, so it reads as one row.
    line_rows, section_of = [rows[0]], [0]
    for n, r in enumerate(rows[1:], start=1):
        lines = ({2: pack_detail, 3: seo_detail}.get(n) or "").split("<br/>")
        # The first row carries two searches: beside one, a two-line area name ("Google Organic Rankings (SEO)")
        # opened a gap. A span would fix it too, but a table will not split inside a span.
        lines = ["<br/>".join(lines[:2])] + lines[2:]
        if len(lines) > 1:
            line_rows.append([r[0], r[1], cell(lines[0])])
            line_rows += [["", "", cell(x)] for x in lines[1:]]
        else:
            line_rows.append(r)
        section_of += [n] * (len(line_rows) - len(section_of))
    rows = line_rows

    # When the searches ran, and Google's ad records for their website (scripts/ads_records.py), as the table's own
    # last row (Welton 2026-10-22; moved into the table 2026-10-29): kept on the same page as the row above it
    # (NOSPLIT), so the note never sits alone at the top of a page away from the table it explains.
    note = Paragraph(escape(measured.searched_line(results)) + "<br/>Google Ads: "
                     + escape(ads_records.line(results.get("ads_records"))), ParagraphStyle(
        "searched", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=9, leading=11,
        textColor=colors.black))
    sc = Table(
        rows + [[note, "", ""]],
        repeatRows=1,
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
        ("BOX", (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ("LINEAFTER", (0, 0), (-2, -2), 0.5, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i, row in enumerate(rows[1:], start=1):
        g = row[1]
        style.append(("TEXTCOLOR", (1, i), (1, i), GRADE_COLORS.get(g, RRM_GRAY)))
    for i in range(1, len(rows)):
        bg = [colors.white, RRM_LIGHT][(section_of[i] - 1) % 2]
        style.append(("BACKGROUND", (0, i), (-1, i), bg))
        if section_of[i] == section_of[i - 1]:
            style += [("TOPPADDING", (0, i), (-1, i), 0), ("BOTTOMPADDING", (0, i - 1), (-1, i - 1), 0)]
        else:
            style.append(("LINEABOVE", (0, i), (-1, i), 0.5, colors.lightgrey))
    style += [("SPAN", (0, -1), (-1, -1)), ("NOSPLIT", (0, -2), (-1, -1)),
              ("LEFTPADDING", (0, -1), (-1, -1), 0), ("TOPPADDING", (0, -1), (-1, -1), 3),
              ("BOTTOMPADDING", (0, -1), (-1, -1), 0)]      # the same height as the old note under the table
    sc.setStyle(TableStyle(style))
    story.append(sc)
    story.append(Spacer(1, 8))

    # Nothing measured to say: no section at all, never a sentence built on a failed search.
    recs = build_recommendations(results)
    CTAFooterCanvas.gaps_measured = bool(recs)
    for i, rec in enumerate(recs):
        # A bullet never splits across two pages, and the heading travels with the first one (Welton 2026-10-22:
        # a line and a half of a bullet sat alone on page 3; the heading alone ended a page).
        story.append(KeepTogether(([Paragraph("WHERE YOUR INQUIRIES ARE GOING", h_section)] if i == 0 else [])
                                  + [Paragraph(f"&bull; {rec}", rec_style)]))
    story.append(Spacer(1, 10))

    try:
        CTAFooterCanvas.qr_png_bytes = generate_qr_png_bytes(CALENDLY_URL)
    except Exception as e:
        print(f"QR generation failed: {e}")
        CTAFooterCanvas.qr_png_bytes = None

    # A trailing Spacer that does not fit at the foot of the last page starts a page of its own, which then
    # carries only the footer bar (the La Paloma sheet, 2026-10-20: "Page 3 is blank except the footer").
    while story and isinstance(story[-1], Spacer):
        story.pop()
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
