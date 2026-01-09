from supabase import create_client, Client
from pdf_service import generate_pdf
import os
from dotenv import load_dotenv

# ===============================
# LOAD ENV VARIABLES
# ===============================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Supabase environment variables not configured properly")

# ===============================
# INITIALIZE SUPABASE CLIENT
# ===============================

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ===============================
# CORE REPORT GENERATOR
# ===============================

def generate_doctor_report(doctor_id: str, summary_json_path: str, language: str = "en"):
    """
    Fetch doctor info from Supabase and generate a PDF report
    """

    try:
        response = (
            supabase
            .table("doctors")
            .select("full_name, degree, clinic_name, medical_id, phone_number, work_location")
            .eq("id", doctor_id)
            .execute()
        )

        if not response.data:
            print(f"❌ Doctor not found: {doctor_id}")
            return None

        doctor_info = response.data[0]

        pdf_path = generate_pdf(
            summary_json_path=summary_json_path,
            doctor_info=doctor_info,
            language=language
        )

        print(f"✅ PDF generated successfully: {pdf_path}")
        return pdf_path

    except Exception as e:
        print(f"❌ Doctor report error: {e}")
        return None
