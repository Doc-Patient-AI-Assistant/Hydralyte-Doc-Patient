import json
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ===============================
# BASE PATHS
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "pdfs")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

os.makedirs(PDF_DIR, exist_ok=True)

# ===============================
# FONT MAP (LANGUAGE → FONT FILE)
# ===============================
FONT_MAP = {
    "hi": "NotoSansDevanagari-Regular.ttf",
    "mr": "NotoSansDevanagari-Regular.ttf",
    "gu": "NotoSansGujarati-Regular.ttf",
    "ta": "NotoSansTamil-Regular.ttf",
    "te": "NotoSansTelugu-Regular.ttf",
    "kn": "NotoSansKannada-Regular.ttf",
    "ml": "NotoSansMalayalam-Regular.ttf",
    "bn": "NotoSansBengali-Regular.ttf",
}

# ===============================
# FONT REGISTRATION (SAFE)
# ===============================
def register_font(language: str) -> str:
    """
    Returns a ReportLab-safe font name.
    English uses Helvetica (built-in).
    Indian languages use proper Noto Sans Unicode fonts.
    """

    # ✅ English → built-in font
    if language == "en":
        return "Helvetica"

    font_file = FONT_MAP.get(language)

    if not font_file:
        print("⚠ No font mapping found, falling back to Helvetica")
        return "Helvetica"

    font_path = os.path.join(FONTS_DIR, font_file)
    font_name = font_file.replace(".ttf", "")

    try:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception as e:
        print("⚠ Font registration failed, fallback to Helvetica:", e)
        return "Helvetica"

# ===============================
# PDF GENERATOR
# ===============================
def generate_pdf(summary_json_path: str, language: str = "en") -> str:
    # -------- LOAD SUMMARY JSON --------
    with open(summary_json_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    base_name = os.path.splitext(os.path.basename(summary_json_path))[0]
    pdf_path = os.path.join(PDF_DIR, f"{base_name}.pdf")

    # -------- REGISTER FONT --------
    font_name = register_font(language)

    # -------- PDF DOCUMENT --------
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    base_styles = getSampleStyleSheet()

    styles = {
        "heading": ParagraphStyle(
            "heading",
            parent=base_styles["Heading3"],
            fontName=font_name,
            spaceAfter=8,
        ),
        "normal": ParagraphStyle(
            "normal",
            parent=base_styles["Normal"],
            fontName=font_name,
            spaceAfter=4,
        ),
    }

    story = []

    # -------- SAFE PARAGRAPH HELPER --------
    def safe_para(text):
        """
        Ensures text is safe for ReportLab Paragraph
        """
        if not text:
            return "—"
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # -------- SECTION HELPER --------
    def add_section(title, content):
        story.append(Paragraph(f"<b>{safe_para(title)}</b>", styles["heading"]))
        story.append(Spacer(1, 6))

        if isinstance(content, list):
            if not content:
                story.append(Paragraph("—", styles["normal"]))
            else:
                for item in content:
                    story.append(
                        Paragraph(f"• {safe_para(item)}", styles["normal"])
                    )
        else:
            story.append(Paragraph(safe_para(content), styles["normal"]))

        story.append(Spacer(1, 14))

    # -------- PDF CONTENT --------
    add_section("Doctor Summary", summary.get("doctor_summary", ""))
    add_section("Symptoms", summary.get("symptoms", []))
    add_section("Patient History", summary.get("patient_history", []))
    add_section("Risk Factors", summary.get("risk_factors", []))
    add_section("Prescription", summary.get("prescription", []))
    add_section("Advice", summary.get("advice", []))
    add_section("Recommended Action", summary.get("recommended_action", ""))

    # -------- BUILD PDF --------
    doc.build(story)

    return pdf_path
