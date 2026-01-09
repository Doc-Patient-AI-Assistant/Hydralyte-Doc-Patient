import json
import os
from datetime import datetime

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
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
# FONT MAP
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
# FONT REGISTRATION
# ===============================
def register_font(language: str) -> str:
    if language == "en":
        return "Helvetica"

    font_file = FONT_MAP.get(language)
    if not font_file:
        return "Helvetica"

    font_path = os.path.join(FONTS_DIR, font_file)
    font_name = font_file.replace(".ttf", "")

    try:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception:
        return "Helvetica"

# ===============================
# SAFE TEXT
# ===============================
def safe_text(text):
    if not text:
        return "—"
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

# ===============================
# LETTERHEAD
# ===============================
def add_letterhead(story, font_name, doctor_info):
    """
    Creates professional letterhead with doctor information
    
    doctor_info should contain:
    - full_name
    - degree
    - clinic_name
    - medical_id
    - phone_number
    - work_location
    """
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "title",
        fontName=font_name,
        fontSize=16,
        alignment=1,
        spaceAfter=4,
        textColor=colors.HexColor("#2F80ED"),
    )

    sub = ParagraphStyle(
        "sub",
        fontName=font_name,
        fontSize=10,
        alignment=1,
        spaceAfter=2,
    )

    # Doctor name and degree
    story.append(
        Paragraph(
            f"<b>{safe_text(doctor_info.get('full_name', 'Dr. Unknown'))}</b>", 
            title
        )
    )
    
    story.append(
        Paragraph(
            safe_text(doctor_info.get('degree', '')), 
            sub
        )
    )
    
    # Clinic name
    story.append(
        Paragraph(
            safe_text(doctor_info.get('clinic_name', '')), 
            sub
        )
    )
    
    # Registration and contact info
    contact_info = f"Reg No: {doctor_info.get('medical_id', 'N/A')}"
    
    if doctor_info.get('phone_number'):
        contact_info += f" | +91 {doctor_info.get('phone_number')}"
    
    if doctor_info.get('work_location'):
        contact_info += f" | {doctor_info.get('work_location')}"
    
    story.append(Paragraph(contact_info, sub))

    story.append(Spacer(1, 10))

    # Blue divider line
    story.append(
        Table(
            [[""]],
            colWidths=[480],
            style=[
                ("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#2F80ED"))
            ],
        )
    )
    
    story.append(Spacer(1, 16))


# ===============================
# PDF GENERATOR
# ===============================
def generate_pdf(
    summary_json_path: str, 
    doctor_info: dict, 
    language: str = "en"
) -> str:
    """
    Generate PDF with doctor information from database
    
    Args:
        summary_json_path: Path to the summary JSON file
        doctor_info: Dictionary containing doctor details from database:
            - full_name
            - degree
            - clinic_name
            - medical_id
            - phone_number
            - work_location
        language: Language code for font selection
    
    Returns:
        Path to generated PDF
    """
    
    # Load summary
    with open(summary_json_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    base_name = os.path.splitext(os.path.basename(summary_json_path))[0]
    pdf_path = os.path.join(PDF_DIR, f"{base_name}.pdf")

    font_name = register_font(language)

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
            fontSize=12,
            textColor=colors.HexColor("#2F80ED"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "normal": ParagraphStyle(
            "normal",
            parent=base_styles["Normal"],
            fontName=font_name,
            fontSize=10,
            spaceAfter=4,
        ),
        "rx": ParagraphStyle(
            "rx",
            parent=base_styles["Normal"],
            fontName=font_name,
            fontSize=10,
            leftIndent=18,
            spaceAfter=6,
        ),
    }

    story = []

    # Letterhead with real doctor info
    add_letterhead(story, font_name, doctor_info)

    def add_section(title, content, rx=False):
        story.append(Paragraph(f"<b>{safe_text(title)}</b>", styles["heading"]))
        story.append(Spacer(1, 4))

        if isinstance(content, list):
            if not content:
                story.append(Paragraph("—", styles["normal"]))
            else:
                for item in content:
                    style = styles["rx"] if rx else styles["normal"]
                    prefix = "• " if rx else "• "
                    story.append(
                        Paragraph(prefix + safe_text(item), style)
                    )
        else:
            story.append(Paragraph(safe_text(content), styles["normal"]))
        story.append(Spacer(1, 12))

    # CONTENT
    add_section("Doctor Summary", summary.get("doctor_summary", ""))
    add_section("Symptoms", summary.get("symptoms", []))
    add_section("Patient History", summary.get("patient_history", []))
    add_section("Risk Factors", summary.get("risk_factors", []))
    add_section("Prescription", summary.get("prescription", []), rx=True)
    add_section("Advice", summary.get("advice", []))
    add_section("Recommended Action", summary.get("recommended_action", ""))

    # FOOTER with signature
    signature_block = KeepTogether([
        Spacer(1, 30),

        Paragraph(
            f"Date: {datetime.now().strftime('%d %b %Y')}",
            ParagraphStyle(
                "date",
                fontName=font_name,
                fontSize=10,
                alignment=2,
            ),
        ),

        Spacer(1, 18),

        Paragraph(
            "Signature:",
            ParagraphStyle(
                "sign_label",
                fontName=font_name,
                fontSize=10,
                alignment=2,
            ),
        ),

        Spacer(1, 22),

        Paragraph(
            "______________________________",
            ParagraphStyle(
                "sign_line",
                fontName=font_name,
                fontSize=10,
                alignment=2,
            ),
        ),

        Spacer(1, 6),

        Paragraph(
            f"<b>{safe_text(doctor_info.get('full_name', 'Dr. Unknown'))}</b>",
            ParagraphStyle(
                "sign_name",
                fontName=font_name,
                fontSize=10,
                alignment=2,
            ),
        ),
    ])

    story.append(signature_block)

    doc.build(story)
    return pdf_path


# ===============================
# EXAMPLE USAGE
# ===============================
if __name__ == "__main__":
    # Example doctor info from Supabase
    doctor_data = {
        "full_name": "Dr. Rajesh Kumar",
        "degree": "MBBS, MD (Internal Medicine)",
        "clinic_name": "Kumar Multispeciality Clinic",
        "medical_id": "MMC/2024/12345",
        "phone_number": "9876543210",
        "work_location": "Mumbai, Maharashtra"
    }
    
    # Generate PDF
    pdf_path = generate_pdf(
        "path/to/summary.json",
        doctor_data,
        language="en"
    )
    
    print(f"PDF generated: {pdf_path}")