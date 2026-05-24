"""
Generate OCR image-format test documents for Sentinel E2E tests.
Produces PNG, JPG, and TIFF files covering diverse scenarios:
  - High-quality clean scans
  - Stamped / watermarked documents
  - Low-resolution noisy scans (OCR stress test)
  - Two-column scanned layout
  - PII in image (guardrail via OCR)
  - Expired documents
  - Missing-clause documents
  - Multi-language (French)

Requires: Pillow (pip install pillow)
Run:  python generate_ocr_test_docs.py
"""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
FONT_DIR = Path("C:/Windows/Fonts")

# ── Font helpers ──────────────────────────────────────────────────────────────

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)

def _reg(size: int = 20) -> ImageFont.FreeTypeFont:
    return _font("times.ttf", size)

def _bold(size: int = 20) -> ImageFont.FreeTypeFont:
    return _font("timesbd.ttf", size)

def _mono(size: int = 18) -> ImageFont.FreeTypeFont:
    return _font("cour.ttf", size)


# ── Core renderer ─────────────────────────────────────────────────────────────

class DocRenderer:
    """Renders a document as a white-page image with typed text."""

    PAGE_W  = 2480   # A4 at 300 DPI
    PAGE_H  = 3508
    MARGIN  = 180
    LINE_H  = 36     # line height for 20pt font
    BG      = (255, 255, 255)
    FG      = (20, 20, 20)

    def __init__(self, dpi_scale: float = 1.0, noise: float = 0.0):
        """
        dpi_scale: 1.0 = 300 DPI (crisp), 0.25 = 75 DPI (blurry after downscale)
        noise:     0.0 = clean, 0.5 = moderately noisy scan
        """
        self.w      = int(self.PAGE_W * dpi_scale)
        self.h      = int(self.PAGE_H * dpi_scale)
        self.lh     = max(12, int(self.LINE_H * dpi_scale))
        self.margin = int(self.MARGIN * dpi_scale)
        self.noise  = noise
        self.scale  = dpi_scale

        self.img  = Image.new("RGB", (self.w, self.h), self.BG)
        self.draw = ImageDraw.Draw(self.img)
        self.y    = self.margin

        # Default fonts
        base_pt = max(8, int(20 * dpi_scale))
        self.f_reg  = _reg(base_pt)
        self.f_bold = _bold(base_pt)
        self.f_h1   = _bold(max(10, int(26 * dpi_scale)))
        self.f_h2   = _bold(max(9, int(22 * dpi_scale)))
        self.f_mono = _mono(max(8, int(18 * dpi_scale)))

    def _text_w(self, text: str, font) -> int:
        bbox = self.draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def title(self, text: str):
        w = self._text_w(text, self.f_h1)
        x = (self.w - w) // 2
        self.draw.text((x, self.y), text, font=self.f_h1, fill=self.FG)
        self.y += int(self.lh * 1.6)

    def section(self, text: str):
        self.y += int(self.lh * 0.4)
        self.draw.text((self.margin, self.y), text, font=self.f_h2, fill=(0, 30, 100))
        self.y += int(self.lh * 1.4)

    def para(self, text: str, font=None, indent: int = 0):
        if font is None:
            font = self.f_reg
        max_w = self.w - 2 * self.margin - indent
        words = text.split()
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if self._text_w(test, font) <= max_w:
                line = test
            else:
                if line:
                    self.draw.text((self.margin + indent, self.y), line, font=font, fill=self.FG)
                    self.y += self.lh
                    if self.y + self.lh > self.h - self.margin:
                        return  # clip bottom
                line = word
        if line:
            self.draw.text((self.margin + indent, self.y), line, font=font, fill=self.FG)
            self.y += self.lh

    def blank(self, lines: int = 1):
        self.y += int(self.lh * lines)

    def rule(self):
        self.y += int(self.lh * 0.3)
        self.draw.line([(self.margin, self.y), (self.w - self.margin, self.y)],
                       fill=(180, 180, 180), width=max(1, int(2 * self.scale)))
        self.y += int(self.lh * 0.6)

    def stamp(self, text: str = "APPROVED", color=(0, 120, 0)):
        """Draw a diagonal rubber-stamp overlay."""
        size = max(60, int(160 * self.scale))
        overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        try:
            sf = _bold(size)
        except Exception:
            sf = self.f_h1
        tw, th = self._text_w(text, sf), size
        cx, cy = self.w // 2, self.h // 2
        temp = Image.new("RGBA", (tw + 40, th + 20), (0, 0, 0, 0))
        td   = ImageDraw.Draw(temp)
        td.rectangle([0, 0, tw + 39, th + 19], outline=(*color, 120), width=max(3, int(8 * self.scale)))
        td.text((20, 10), text, font=sf, fill=(*color, 100))
        rotated = temp.rotate(30, expand=True)
        rx = cx - rotated.width  // 2
        ry = cy - rotated.height // 2
        overlay.paste(rotated, (rx, ry), rotated)
        self.img = Image.alpha_composite(self.img.convert("RGBA"), overlay).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

    def watermark(self, text: str = "DRAFT"):
        """Diagonal light watermark across the entire page."""
        size = max(80, int(220 * self.scale))
        wm   = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        wd   = ImageDraw.Draw(wm)
        try:
            wf = _bold(size)
        except Exception:
            wf = self.f_h1
        tw = self._text_w(text, wf)
        for step_x in range(-self.w, 2 * self.w, tw + int(200 * self.scale)):
            for step_y in range(-self.h, 2 * self.h, size + int(200 * self.scale)):
                wd.text((step_x, step_y), text, font=wf, fill=(200, 0, 0, 28))
        rotated = wm.rotate(35, expand=False)
        rotated = rotated.crop((0, 0, self.w, self.h))
        self.img = Image.alpha_composite(self.img.convert("RGBA"), rotated).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

    def add_scan_noise(self):
        """Add speckle noise to simulate a real scanned page."""
        import random as _r
        pixels = self.img.load()
        n_spots = int(self.w * self.h * self.noise * 0.002)
        for _ in range(n_spots):
            x = _r.randint(0, self.w - 1)
            y = _r.randint(0, self.h - 1)
            shade = _r.randint(0, 180)
            pixels[x, y] = (shade, shade, shade)

    def save(self, name: str, fmt: str = "PNG", quality: int = 85):
        """Save the image. fmt: 'PNG', 'JPEG', 'TIFF'"""
        if self.noise > 0:
            self.add_scan_noise()
        out = OUT / name
        if fmt == "JPEG":
            self.img.save(str(out), "JPEG", quality=quality, dpi=(300, 300))
        elif fmt == "TIFF":
            self.img.save(str(out), "TIFF", compression="tiff_lzw", dpi=(300, 300))
        else:
            self.img.save(str(out), "PNG", dpi=(300, 300))
        print(f"  Created: {name}  ({out.stat().st_size // 1024} KB)")
        return out


# ── Document generators ───────────────────────────────────────────────────────

def make_credit_png_approved():
    """PNG — Clean high-quality credit agreement scan, all 4 clauses."""
    r = DocRenderer(dpi_scale=0.9, noise=0.02)
    r.title("TERM LOAN AGREEMENT")
    r.para("This Term Loan Agreement is entered into as of June 1, 2026, between "
           "FIRST NATIONAL LENDING CORP. ('Lender') and BRIDGEWATER CONSTRUCTION LLC ('Borrower'). "
           "Facility Amount: USD 8,500,000. Maturity: 60 months from drawdown date.")
    r.rule()

    r.section("SECTION 1 — GOVERNING LAW CLAUSE")
    r.para("This Agreement shall be governed by and construed in accordance with the laws of the "
           "State of New York, excluding conflict-of-law principles. Each party irrevocably submits "
           "to the exclusive jurisdiction of the state and federal courts in New York County.")
    r.para("Jury Waiver: Each party waives all rights to a jury trial in any proceeding "
           "arising from or relating to this Agreement or the transactions contemplated herein.")

    r.section("SECTION 2 — EVENTS OF DEFAULT CLAUSE")
    r.para("Each of the following constitutes an Event of Default: (a) failure to pay principal or "
           "interest within five business days of the due date; (b) material breach of any covenant "
           "not cured within 30 days of written notice; (c) voluntary or involuntary bankruptcy or "
           "insolvency proceedings; (d) cross-default exceeding USD 500,000; (e) material adverse "
           "change in Borrower's financial condition; (f) change of control without prior consent.")
    r.para("Upon default, Lender may declare all outstanding amounts immediately due and payable "
           "and exercise all rights and remedies available at law or in equity.")

    r.section("SECTION 3 — INDEMNIFICATION CLAUSE")
    r.para("Borrower shall indemnify, defend, and hold harmless Lender and its officers, directors, "
           "employees, and agents from and against any and all claims, losses, damages, liabilities, "
           "costs, and expenses (including reasonable attorneys' fees) arising from: (a) any breach "
           "of this Agreement; (b) inaccuracy of any representation or warranty; (c) use of loan "
           "proceeds; (d) any third-party claim arising from Borrower's business operations.")
    r.para("Indemnification obligations survive full repayment of the loan for a period of 3 years.")

    r.section("SECTION 4 — REPRESENTATIONS AND WARRANTIES")
    r.para("Borrower represents and warrants that: (1) it is duly organised and in good standing; "
           "(2) it has full authority to execute this Agreement; (3) financial statements provided "
           "are accurate and prepared in accordance with U.S. GAAP; (4) no material adverse change "
           "has occurred since the last audited balance sheet date; (5) Borrower is in compliance "
           "with all applicable laws; (6) no material litigation is pending or threatened.")
    r.para("These representations are deemed repeated on each drawdown date and remain true "
           "throughout the term of this Agreement.")

    r.rule()
    r.para("SIGNATURES  |  Lender: Thomas E. Kowalski, SVP — Date: June 1, 2026")
    r.para("Borrower: Patricia A. Novak, CFO, Bridgewater Construction LLC — Date: June 1, 2026")
    r.para("Loan Reference: FNLC-TLA-BWC-2026-088")

    r.save("credit_agreement_png_clean_scan_APPROVED.png", fmt="PNG")


def make_employment_jpg_approved():
    """JPG — Standard scan quality employment contract, all 4 clauses."""
    r = DocRenderer(dpi_scale=0.85, noise=0.04)
    r.title("EMPLOYMENT AGREEMENT — SENIOR VICE PRESIDENT")
    r.para("This Employment Agreement ('Agreement') is made as of July 15, 2026, between "
           "NEXASTREAM FINANCIAL SERVICES INC. ('Company') and DIANA L. HARTWELL ('Executive').")
    r.rule()

    r.section("SECTION 1 — COMPENSATION AND BENEFITS CLAUSE")
    r.para("1.1 Base Salary: USD 320,000 per annum, paid bi-weekly. Annual review by the Board.")
    r.para("1.2 Annual Bonus: Target 50% of base salary (up to 80%) based on performance KPIs "
           "reviewed by the Compensation Committee of the Board of Directors.")
    r.para("1.3 Equity: 400,000 RSUs vesting over 4 years (25% cliff at year 1, monthly thereafter).")
    r.para("1.4 Benefits: Full medical, dental, vision for Executive and dependants; life insurance "
           "2x salary; 401(k) with 5% employer match; 20 days PTO plus public holidays; "
           "USD 5,000 annual professional development allowance.")

    r.section("SECTION 2 — INTELLECTUAL PROPERTY ASSIGNMENT CLAUSE")
    r.para("All inventions, improvements, software, works of authorship, and other intellectual "
           "property created by Executive during employment that relate to the Company's business "
           "or that result from use of Company resources are hereby assigned exclusively to Company. "
           "Executive waives all moral rights to the fullest extent permitted by law. "
           "Pre-existing intellectual property is listed in Exhibit A and is excluded.")

    r.section("SECTION 3 — TERMINATION AND SEVERANCE CLAUSE")
    r.para("3.1 At-Will Employment: Either party may terminate on 60 days written notice.")
    r.para("3.2 Termination Without Cause: Company shall pay 12 months base salary continuation "
           "plus continuation of benefits for 12 months, plus acceleration of 25% of unvested RSUs.")
    r.para("3.3 Termination for Cause: Defined as fraud, misconduct, felony conviction, or material "
           "breach not cured within 15 days. No severance payable on termination for cause.")
    r.para("3.4 Good Reason Resignation: Same severance as termination without cause applies.")

    r.section("SECTION 4 — NON-COMPETE AND CONFIDENTIALITY CLAUSE")
    r.para("4.1 Confidentiality: Executive shall not disclose any Confidential Information during "
           "or after employment. Confidential Information includes all non-public business, "
           "technical, financial, and strategic information of the Company.")
    r.para("4.2 Non-Competition: For 18 months post-separation, Executive shall not serve in "
           "a senior executive role at a direct competitor in the financial technology sector.")
    r.para("4.3 Non-Solicitation: For 24 months post-separation, shall not solicit Company "
           "employees or clients.")

    r.rule()
    r.para("NEXASTREAM FINANCIAL SERVICES INC. — By: Mark O. Sullivan, CEO — July 15, 2026")
    r.para("EXECUTIVE — Diana L. Hartwell — July 15, 2026  |  Ref: NFS-EA-SVP-2026-041")

    r.save("employment_contract_jpg_standard_scan_APPROVED.jpg", fmt="JPEG", quality=82)


def make_regulatory_tiff_approved():
    """TIFF — High-quality scanned regulatory filing, all 3 clauses."""
    r = DocRenderer(dpi_scale=1.0, noise=0.01)
    r.title("ANNUAL REGULATORY FILING — FORM RF-2026")
    r.para("Submitted to: Financial Markets Authority (FMA)  |  Date: August 1, 2026")
    r.para("Registrant: STERLING ASSET MANAGEMENT GROUP PLC  |  CRN: 04827163  |  FCA Ref: 782941")
    r.rule()

    r.section("PART A — MATERIAL DISCLOSURE STATEMENT")
    r.para("This filing constitutes the material disclosure statement required under the Financial "
           "Services and Markets Act 2000 (FSMA) and FMA Disclosure Rules. Sterling Asset Management "
           "Group PLC ('Company') discloses the following material events for the period ended "
           "June 30, 2026:")
    r.para("Material Disclosure 1: The Company completed the acquisition of Harrington Capital "
           "Management Ltd. on April 18, 2026 for total consideration of GBP 287 million. "
           "This represents a material event as defined under FSMA Section 87A.")
    r.para("Material Disclosure 2: Assets under management increased 23% year-over-year to "
           "GBP 18.4 billion as of June 30, 2026. Revenue for H1 2026 was GBP 142.3 million "
           "(H1 2025: GBP 115.6 million). Operating profit: GBP 38.7 million.")
    r.para("Material Disclosure 3: The Board declared an interim dividend of 14.2p per share, "
           "payable September 15, 2026 to shareholders on record as of August 22, 2026.")

    r.section("PART B — RISK FACTOR DISCLOSURES")
    r.para("The following material risk factors are disclosed pursuant to regulatory obligations:")
    r.para("Risk 1 — Market Risk: AUM and revenues are subject to market volatility. A 20% decline "
           "in equity markets would reduce AUM by approximately GBP 3.1 billion and annual "
           "management fee revenue by approximately GBP 6.2 million based on current fee rates.")
    r.para("Risk 2 — Regulatory Risk: Increasing regulatory requirements in the UK and EU may "
           "require significant compliance investment. Post-Brexit divergence creates operational "
           "complexity for cross-border investment management activities.")
    r.para("Risk 3 — Operational and Cyber Risk: The Company invested GBP 12.4 million in "
           "technology infrastructure in H1 2026. A cybersecurity incident could disrupt operations "
           "and damage client relationships.")
    r.para("Risk 4 — Key Personnel Risk: Departure of key investment professionals could adversely "
           "affect fund performance and client retention.")

    r.section("PART C — AUDITOR CERTIFICATION")
    r.para("Independent Registered Auditor Certification Statement:")
    r.para("We, Deloitte LLP, registered auditors (ICAEW No. C001414814), hereby certify that the "
           "financial information contained in this regulatory filing has been prepared in accordance "
           "with UK GAAP and the FCA's Disclosure and Transparency Rules. In our opinion, the "
           "information presents a true and fair view of the financial position of Sterling Asset "
           "Management Group PLC as of June 30, 2026. This auditor certification is provided "
           "pursuant to FCA DTR 4.1.14R.")
    r.para("Signed: Deloitte LLP  |  London, EC4A 3BZ  |  Registered in England No. OC303675")
    r.para("Lead Audit Partner: Sarah J. Clifton, FCA  |  Date: July 28, 2026")

    r.rule()
    r.para("Director Certification: We confirm this filing is accurate and complete to the best of "
           "our knowledge.  CEO: James H. Windsor — CFO: Priya M. Kapoor — Date: August 1, 2026")
    r.para("Filing Reference: SAM-RF-2026-H1-001")

    r.save("regulatory_filing_tiff_clean_scan_APPROVED.tiff", fmt="TIFF")


def make_insurance_png_watermark_approved():
    """PNG — Insurance policy with CONFIDENTIAL watermark, all 4 clauses."""
    r = DocRenderer(dpi_scale=0.88, noise=0.03)
    r.title("COMMERCIAL GENERAL LIABILITY INSURANCE POLICY")
    r.para("Policy No: CGL-2026-US-994421  |  Insurer: GUARDIAN INSURANCE COMPANY OF AMERICA")
    r.para("Insured: RIVERBEND HOSPITALITY GROUP LLC  |  Period: Sep 1, 2026 - Aug 31, 2027")
    r.rule()

    r.section("SECTION 1 — COVERAGE SCOPE AND LIMITS")
    r.para("1.1 Bodily Injury and Property Damage: USD 1,000,000 per occurrence / USD 2,000,000 "
           "general aggregate. Covers claims for bodily injury or property damage arising from "
           "Insured's business operations, premises, or products.")
    r.para("1.2 Personal and Advertising Injury: USD 1,000,000 per person or organization. "
           "Covers libel, slander, invasion of privacy, wrongful eviction, and copyright "
           "infringement in advertising.")
    r.para("1.3 Products/Completed Operations: USD 2,000,000 aggregate. Covers claims arising "
           "from Insured's products or completed work.")
    r.para("1.4 Medical Payments: USD 10,000 per person, regardless of fault, for bodily injury "
           "occurring on Insured's premises.")
    r.para("1.5 Fire Legal Liability: USD 100,000 per occurrence for damage to premises rented "
           "to the Insured.")

    r.section("SECTION 2 — EXCLUSIONS AND LIMITATIONS CLAUSE")
    r.para("This policy does not cover: (a) Expected or intended injury — losses arising from "
           "intentional acts by the Insured; (b) Workers Compensation — employer liability covered "
           "separately; (c) Pollution — environmental contamination; (d) Aircraft, Auto, Watercraft; "
           "(e) War, terrorism, nuclear events; (f) Professional liability and errors and omissions; "
           "(g) Cyber incidents unless Cyber endorsement attached; (h) Contractual liability beyond "
           "insured contracts; (i) Liquor liability if Insured is in the business of selling alcohol "
           "(separate Liquor Liability policy required).")

    r.section("SECTION 3 — CLAIMS PROCEDURE")
    r.para("3.1 Reporting: Insured must notify Guardian Insurance in writing within 30 days of any "
           "occurrence that may give rise to a claim. Notice to: claims@guardianinsurance.com or "
           "1-800-GUARDIAN. Policy No. CGL-2026-US-994421 must be referenced in all communications.")
    r.para("3.2 Cooperation: Insured shall cooperate fully with Guardian Insurance's investigation, "
           "provide all relevant records and documents, and not admit liability or settle any claim "
           "without prior written consent of Guardian Insurance.")
    r.para("3.3 Legal Proceedings: Guardian Insurance reserves the right to defend, investigate, "
           "and settle any covered claim. Insured shall promptly forward all legal papers received.")

    r.section("SECTION 4 — PREMIUM PAYMENT AND CANCELLATION TERMS")
    r.para("4.1 Annual Premium: USD 24,800 payable as: USD 12,400 at inception (Sep 1, 2026) and "
           "USD 12,400 by March 1, 2027. Late payments attract 1.5% monthly interest.")
    r.para("4.2 Cancellation by Insured: 30 days written notice; pro-rata refund of unearned premium.")
    r.para("4.3 Cancellation by Insurer: 10 days notice for non-payment; 30 days for other reasons. "
           "Pro-rata refund of unearned premium. Policy is non-cancellable during active litigation.")

    r.rule()
    r.para("Signed: Guardian Insurance Company of America  |  Underwriter: R. Hamilton  |  Sep 1, 2026")

    r.watermark("CONFIDENTIAL")
    r.save("insurance_policy_png_watermark_approved_APPROVED.png", fmt="PNG")


def make_partnership_jpg_stamp_approved():
    """JPG — Partnership agreement with EXECUTED stamp, all 4 clauses."""
    r = DocRenderer(dpi_scale=0.87, noise=0.05)
    r.title("GENERAL PARTNERSHIP AGREEMENT")
    r.para("This General Partnership Agreement is entered into as of September 1, 2026, between "
           "REDWOOD CAPITAL PARTNERS LLC ('Partner A') and COASTAL PROPERTIES INC. ('Partner B'), "
           "collectively forming REDWOOD COASTAL REAL ESTATE PARTNERS ('Partnership').")
    r.rule()

    r.section("SECTION 1 — CAPITAL CONTRIBUTION CLAUSE")
    r.para("1.1 Initial Contributions: Partner A contributes USD 5,000,000 cash (50% interest). "
           "Partner B contributes USD 3,000,000 cash plus real estate assets valued at USD 2,000,000 "
           "per independent appraisal dated August 15, 2026 (50% interest).")
    r.para("1.2 Capital Accounts: Each partner's capital account is maintained separately. "
           "Returns of capital require unanimous written consent of all partners.")
    r.para("1.3 Additional Capital: Approved by majority vote. Non-contributing partners' interests "
           "diluted proportionally. Right of first refusal applies to any capital call.")

    r.section("SECTION 2 — PROFIT AND LOSS DISTRIBUTION")
    r.para("2.1 Distribution Split: 50% to Partner A, 50% to Partner B. Distributions quarterly "
           "within 30 days of quarter-end, subject to minimum reserve requirements.")
    r.para("2.2 Priority Return: Partner A receives a 7% preferred return on its USD 5,000,000 "
           "cash contribution before general distributions commence in the first year of operations.")
    r.para("2.3 Loss Allocation: Net losses allocated 50/50. Partners liable for losses up to their "
           "capital account balance. No partner required to contribute beyond initial commitment.")

    r.section("SECTION 3 — GOVERNANCE AND VOTING RIGHTS")
    r.para("3.1 Management Committee: Two representatives from each Partner (4 total). Decisions "
           "by simple majority for routine matters; unanimous for extraordinary matters including "
           "capital calls, new partner admission, and dissolution.")
    r.para("3.2 Voting Rights: Each partner holds votes proportional to its partnership interest "
           "(50/50). In case of deadlock, independent arbitrator appointed by AAA.")
    r.para("3.3 Annual Meetings: Management Committee meets quarterly; annual financial review "
           "in February of each year with audited financial statements.")

    r.section("SECTION 4 — DISSOLUTION AND EXIT CLAUSE")
    r.para("4.1 Voluntary Dissolution: Unanimous written consent required. 120 days wind-down "
           "period during which existing business is completed.")
    r.para("4.2 Winding-Up: Assets liquidated at fair market value. Proceeds distributed: first to "
           "creditors, then return of capital contributions, then residual split 50/50.")
    r.para("4.3 Buy-Out: Either partner may purchase the other's interest at fair market value "
           "(independent valuation). Selling partner has 60 days to accept or counter.")
    r.para("4.4 Term: Partnership has an initial 10-year term, renewable by mutual agreement.")

    r.rule()
    r.para("Partner A: REDWOOD CAPITAL PARTNERS LLC — By: Michael R. Chen, Managing Partner — Sep 1, 2026")
    r.para("Partner B: COASTAL PROPERTIES INC. — By: Sarah E. Taylor, President — Sep 1, 2026")

    r.stamp("EXECUTED", color=(0, 100, 0))
    r.save("partnership_agreement_jpg_executed_stamp_APPROVED.jpg", fmt="JPEG", quality=80)


def make_credit_tiff_expired_rejected():
    """TIFF — Expired credit facility, expiry explicitly stated — should be REJECTED."""
    r = DocRenderer(dpi_scale=0.9, noise=0.02)
    r.title("REVOLVING CREDIT FACILITY AGREEMENT")
    r.para("NOTE: THIS FACILITY EXPIRED on March 31, 2022. This document is retained for "
           "archival purposes only and is no longer legally operative.")
    r.rule()
    r.para("This Revolving Credit Facility Agreement was entered into as of April 1, 2018, between "
           "MERIDIAN LENDING BANK ('Lender') and DELTA TRADE LOGISTICS LTD ('Borrower'). "
           "The facility of USD 3,000,000 matured and expired on March 31, 2022.")

    r.section("SECTION 1 — GOVERNING LAW CLAUSE")
    r.para("This Agreement is governed by the laws of England and Wales. The parties submitted to "
           "exclusive jurisdiction of the English courts. Any disputes arising shall be resolved "
           "under the laws of England and Wales without regard to conflict-of-law principles.")

    r.section("SECTION 2 — EVENTS OF DEFAULT CLAUSE")
    r.para("Events of Default included: payment failures, covenant breaches, insolvency, "
           "material adverse change, and cross-default. Upon default, Lender could accelerate "
           "all outstanding amounts and terminate the facility immediately.")

    r.section("SECTION 3 — INDEMNIFICATION CLAUSE")
    r.para("Borrower agreed to indemnify Lender and its officers from all claims, losses, and "
           "expenses arising from breach of this Agreement or use of loan proceeds. Indemnification "
           "survived expiry of the facility for a period of 5 years (until March 31, 2027).")

    r.section("SECTION 4 — REPRESENTATIONS AND WARRANTIES")
    r.para("At origination, Borrower represented that it was duly organised, had full authority, "
           "its financial statements were accurate per UK GAAP, it was in regulatory compliance, "
           "and no material litigation was pending.")

    r.blank()
    r.para("FACILITY EXPIRY CONFIRMATION: This credit facility expired on March 31, 2022 "
           "upon maturity without renewal. All outstanding obligations were settled as of "
           "April 15, 2022. The Lender confirms full and final discharge of all Borrower "
           "obligations as of that date.")
    r.rule()
    r.para("Archived: Meridian Lending Bank — Legal & Compliance Dept. — Ref: MLB-RCF-DT-2018-EXPIRED")

    r.save("credit_agreement_tiff_expired_2022_REJECTED.tiff", fmt="TIFF")


def make_employment_png_missing_noncompete_rejected():
    """PNG — Employment contract missing non-compete/confidentiality clause — REJECTED."""
    r = DocRenderer(dpi_scale=0.9, noise=0.03)
    r.title("EMPLOYMENT AGREEMENT — SOFTWARE ENGINEER")
    r.para("This Agreement is entered into as of October 1, 2026, between "
           "SKYLINE TECH SOLUTIONS PTE. LTD. ('Company') and ARJUN K. SHARMA ('Employee').")
    r.rule()

    r.section("SECTION 1 — COMPENSATION AND BENEFITS CLAUSE")
    r.para("1.1 Salary: SGD 8,500 per month, payable on the last business day of each month.")
    r.para("1.2 Annual Bonus: Discretionary bonus of up to 2 months salary based on performance.")
    r.para("1.3 Benefits: Medical insurance for Employee; 14 days annual leave; 5 days sick leave; "
           "CPF contributions per Singapore CPF Act; flexible work from home arrangements.")
    r.para("1.4 Equipment: Company-issued laptop and software licences provided.")

    r.section("SECTION 2 — INTELLECTUAL PROPERTY ASSIGNMENT CLAUSE")
    r.para("All software code, algorithms, data models, technical documentation, and other "
           "intellectual property created by Employee in the course of employment, using Company "
           "resources, or related to the Company's business, are hereby assigned to the Company. "
           "Employee retains ownership of pre-existing personal projects listed in Schedule A.")

    r.section("SECTION 3 — TERMINATION AND SEVERANCE CLAUSE")
    r.para("3.1 Notice Period: Either party may terminate this Agreement by providing one (1) month "
           "written notice, or payment in lieu of notice at the Company's election.")
    r.para("3.2 Severance: No severance is payable other than salary in lieu of notice and any "
           "accrued and unpaid salary, bonus, and CPF contributions.")
    r.para("3.3 Summary Termination: Company may terminate immediately without notice for gross "
           "misconduct, fraud, or serious breach of employment terms.")

    r.section("SECTION 5 — GENERAL PROVISIONS")
    r.para("[NOTE: This agreement intentionally omits any non-compete or confidentiality clause. "
           "The Company relies on Singapore's common law implied duty of fidelity during employment "
           "only. There is no post-employment restraint of trade or confidentiality obligation.]")
    r.para("Governing Law: Singapore. Entire Agreement. Amendments in writing only.")

    r.rule()
    r.para("SKYLINE TECH SOLUTIONS PTE. LTD. — By: Lim Wei Ming, CEO — Oct 1, 2026")
    r.para("EMPLOYEE — Arjun K. Sharma — Oct 1, 2026  |  Ref: STS-EA-SWE-2026-077")

    r.save("employment_contract_png_missing_noncompete_REJECTED.png", fmt="PNG")


def make_pii_scan_jpg_blocked():
    """JPG — Scanned document with PII (SSN + credit card) — guardrail must block after OCR."""
    r = DocRenderer(dpi_scale=0.85, noise=0.05)
    r.title("EMPLOYEE ONBOARDING FORM")
    r.para("Company: DELTA FINANCIAL SERVICES INC.  |  Date: October 15, 2026")
    r.rule()

    r.section("PERSONAL INFORMATION")
    r.para("Full Name: Robert James McAllister")
    r.para("Date of Birth: March 14, 1985")
    r.para("Social Security Number: 372-84-9156")
    r.para("Home Address: 4521 Maple Drive, Austin, TX 78701")
    r.para("Email: r.mcallister@personal.com  |  Phone: (512) 555-0183")

    r.section("PAYMENT DETAILS")
    r.para("Payment Method: Corporate Credit Card for business expenses")
    r.para("Card Number: 4532015112830366")
    r.para("Card Holder: Robert J McAllister  |  Expiry: 09/28  |  CVV: 847")
    r.para("Bank Account for Payroll: Routing 021000021  |  Account 8834927651")

    r.section("EMERGENCY CONTACT")
    r.para("Name: Jennifer McAllister (Spouse)")
    r.para("Relationship: Spouse  |  Phone: (512) 555-0292")

    r.section("ACKNOWLEDGMENT")
    r.para("I confirm the above information is accurate and authorise Delta Financial Services Inc. "
           "to use this information for payroll, benefits, and corporate account setup.")
    r.blank()
    r.para("Signature: ___________________  Date: October 15, 2026")
    r.rule()
    r.para("FOR HR USE ONLY — Employee ID: DF-2026-1042  |  Start Date: November 1, 2026")

    r.save("guardrail_pii_ssn_creditcard_scanned_image_BLOCKED.jpg", fmt="JPEG", quality=78)


def make_legal_png_lowres_rejected():
    """PNG — Very low resolution scan — OCR extracts minimal text — expect REJECTED (missing clauses)."""
    r = DocRenderer(dpi_scale=0.22, noise=0.08)  # ~66 DPI — OCR-challenging
    r.title("NON-DISCLOSURE AGREEMENT")
    r.para("This NDA is between ALPHA CORP and BETA SOLUTIONS INC. dated November 1, 2026.")
    r.blank()
    r.section("SECTION 1 - FORCE MAJEURE")
    r.para("Neither party liable for delays caused by force majeure events beyond reasonable control.")
    r.blank()
    r.section("SECTION 2 - LIABILITY")
    r.para("Liability limited to amounts paid in prior 12 months. No consequential damages.")
    r.blank()
    r.section("SECTION 3 - DISPUTES")
    r.para("Disputes resolved by arbitration under AAA rules in New York, New York.")
    r.blank()
    r.para("ALPHA CORP: John Smith — BETA SOLUTIONS: Jane Doe — Date: Nov 1 2026")

    # Scale up to A4 size (simulates low-DPI scan blown up to standard size)
    img_small = r.img
    full = img_small.resize((DocRenderer.PAGE_W, DocRenderer.PAGE_H), Image.NEAREST)
    r.img = full
    r.save("legal_contract_png_lowres_scan_REJECTED.png", fmt="PNG")


def make_partnership_tiff_french_warning():
    """TIFF — French-language scanned partnership agreement — language warning expected."""
    r = DocRenderer(dpi_scale=0.88, noise=0.03)
    r.title("ACCORD DE PARTENARIAT")
    r.para("Le present Accord de Partenariat est conclu le 1er novembre 2026 entre "
           "LUMIERE CAPITAL SAS (France) et BOREALIS INVESTISSEMENTS INC. (Canada).")
    r.rule()

    r.section("ARTICLE 1 — APPORT EN CAPITAL")
    r.para("1.1 Apports initiaux: Lumiere Capital SAS apporte EUR 4 000 000 en numeraire (50%). "
           "Borealis Investissements Inc. apporte EUR 3 000 000 en numeraire et des actifs "
           "immobiliers evalues EUR 1 000 000 par expert independant (50%).")
    r.para("1.2 Comptes de capital: Maintenus separement pour chaque associe. "
           "Les retraits de capital necessitent l'accord unanime des associes.")

    r.section("ARTICLE 2 — REPARTITION DES BENEFICES ET DES PERTES")
    r.para("2.1 Distribution des benefices: 50% a Lumiere Capital, 50% a Borealis. "
           "Distribution trimestrielle dans les 30 jours suivant la cloture du trimestre.")
    r.para("2.2 Imputation des pertes: Reparties a 50/50 dans la limite des apports en capital.")

    r.section("ARTICLE 3 — GOUVERNANCE ET DROITS DE VOTE")
    r.para("3.1 Comite de direction: Deux representants de chaque associe. "
           "Decisions ordinaires a la majorite simple; decisions extraordinaires a l'unanimite.")
    r.para("3.2 President: Nomme alternativement par chaque associe pour un mandat de 12 mois.")

    r.section("ARTICLE 4 — DISSOLUTION ET SORTIE")
    r.para("4.1 Dissolution volontaire: Accord unanime requis. Periode de liquidation de 90 jours.")
    r.para("4.2 Liquidation: Actifs liquides a la valeur marchande; produits distribues aux "
           "creanciers en priorite, puis retour des apports, puis partage residuel 50/50.")
    r.para("4.3 Droit de rachat: Tout associe peut racheter la part de l'autre a la valeur "
           "marchande evaluee par expert independant. Delai d'acceptation: 60 jours.")

    r.rule()
    r.para("Lumiere Capital SAS — Sophie Beaumont, PDG — 1er novembre 2026")
    r.para("Borealis Investissements Inc. — Jean-Pierre Lafleur, President — 1er novembre 2026")
    r.para("Reference: LCBR-AP-2026-001")

    r.save("partnership_agreement_tiff_french_scan_WARNING.tiff", fmt="TIFF")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating OCR image test documents...")
    make_credit_png_approved()
    make_employment_jpg_approved()
    make_regulatory_tiff_approved()
    make_insurance_png_watermark_approved()
    make_partnership_jpg_stamp_approved()
    make_credit_tiff_expired_rejected()
    make_employment_png_missing_noncompete_rejected()
    make_pii_scan_jpg_blocked()
    make_legal_png_lowres_rejected()
    make_partnership_tiff_french_warning()
    print("Done. 10 OCR test files created.")
