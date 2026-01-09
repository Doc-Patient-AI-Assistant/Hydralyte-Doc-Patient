from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from language_service import translate_text
from doctor_report_service import generate_doctor_report

import os
import shutil
import json
import uuid
import threading
import time
from dotenv import load_dotenv
from pydub import AudioSegment
from typing import Optional

# ================= LOAD ENV =================
load_dotenv()

# ================= FFMPEG =================
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffprobe = FFPROBE_PATH

# ================= SERVICES =================
from assembly_service import transcribe_audio
from groq_service import generate_summary
from pdf_service import generate_pdf

# ================= APP =================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= ROBOT AUTHENTICATION =================
ALLOWED_ROBOT_MAC = "D0:39:FA:9C:62:E3"
ROBOT_API_KEY = os.getenv("ROBOT_API_KEY", "robot_secret_key_12345")

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")
SUMMARIES_DIR = os.path.join(BASE_DIR, "summaries")
PDFS_DIR = os.path.join(BASE_DIR, "pdfs")

STATUS_FILE = os.path.join(BASE_DIR, "status.json")

for d in [UPLOAD_DIR, PROCESSED_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR, PDFS_DIR]:
    os.makedirs(d, exist_ok=True)

# ================= GLOBAL LOCK =================
PIPELINE_LOCK = threading.Lock()

# ================= ROBOT SESSION STORAGE =================
robot_sessions = {}  # {session_id: {"status": "recording", "start_time": timestamp}}

# ================= STATUS =================
def write_status(data):
    data["timestamp"] = int(time.time())
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.get("/status")
def get_status():
    if not os.path.exists(STATUS_FILE):
        return {"stage": "idle"}
    with open(STATUS_FILE, encoding="utf-8") as f:
        return json.load(f)

# ================= AUDIO PREPROCESS =================
def preprocess_audio(input_path, output_wav):
    print(f"🎧 Preprocessing: {input_path}", flush=True)
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_wav, format="wav")
    del audio

# ================= ROLE-BASED FORMATTER =================
def format_role_based_text(utterances):
    if not utterances:
        return ""
    speaker_lengths = {}
    for u in utterances:
        speaker_lengths[u["speaker"]] = speaker_lengths.get(u["speaker"], 0) + len(u["text"])
    doctor_speaker = max(speaker_lengths, key=speaker_lengths.get)
    return "\n".join(f"{'Doctor' if u['speaker']==doctor_speaker else 'Patient'}: {u['text']}" for u in utterances)

def detect_language_from_text(text):
    return "hi" if any("\u0900" <= ch <= "\u097F" for ch in text) else "en"

# ================= CORE PIPELINE =================
def process_audio_pipeline(wav_path, base_name, source, doctor_id):

    with PIPELINE_LOCK:
        try:
            print(f"🚀 PIPELINE START: {base_name} (source: {source})", flush=True)
            write_status({"source": source, "file": base_name, "stage": "transcribing"})

            transcript = transcribe_audio(wav_path)
            if not transcript or not transcript.text.strip():
                raise RuntimeError("Empty transcription")

            language = detect_language_from_text(transcript.text)
            utterances = [{"speaker": u.speaker, "text": u.text, "start_ms": u.start, "end_ms": u.end}
                          for u in (transcript.utterances or [])]

            transcript_json = {
                "audio_file": base_name,
                "language": language,
                "full_text": format_role_based_text(utterances),
                "utterances": utterances
            }

            tpath = os.path.join(TRANSCRIPTS_DIR, f"{base_name}.json")
            with open(tpath, "w", encoding="utf-8") as f:
                json.dump(transcript_json, f, indent=2, ensure_ascii=False)

            write_status({"source": source, "file": base_name, "language": language, "stage": "summarizing"})

            summary_en = generate_summary(transcript_json)
            if not summary_en:
                raise RuntimeError("Summary failed")

            summary_final = {k: [translate_text(i, language) for i in v] if isinstance(v, list)
                             else translate_text(v, language)
                             for k, v in summary_en.items()} if language != "en" else summary_en

            spath = os.path.join(SUMMARIES_DIR, f"{base_name}_summary.json")
            with open(spath, "w", encoding="utf-8") as f:
                json.dump(summary_final, f, indent=2, ensure_ascii=False)

            write_status({"source": source, "file": base_name, "language": language, "stage": "generating_pdf"})

            generate_doctor_report(
                doctor_id=doctor_id,
                summary_json_path=spath,
                language=language
            )

            write_status({"source": source, "file": base_name, "language": language, "stage": "completed"})
            print(f"✅ PIPELINE COMPLETED: {base_name}", flush=True)

        except Exception as e:
            print(f"❌ PIPELINE ERROR: {e}", flush=True)
            write_status({"source": source, "file": base_name, "stage": "error", "error": str(e)})

# ================= ROBOT AUTHENTICATION HELPER =================
def verify_robot(mac_address: Optional[str], api_key: Optional[str]) -> bool:
    if not mac_address or not api_key:
        return False

    mac_normalized = mac_address.upper().replace("-", ":").replace(".", ":")
    allowed_mac = ALLOWED_ROBOT_MAC.upper().replace("-", ":").replace(".", ":")

    return mac_normalized == allowed_mac and api_key == ROBOT_API_KEY

# ================= ROBOT API ENDPOINTS =================

@app.post("/robot/start-recording")
async def robot_start_recording(
    mac_address: Optional[str] = Header(None, alias="X-Robot-MAC"),
    api_key: Optional[str] = Header(None, alias="X-Robot-API-Key")
):
    if not verify_robot(mac_address, api_key):
        raise HTTPException(status_code=403, detail="Unauthorized robot device")

    session_id = uuid.uuid4().hex
    robot_sessions[session_id] = {
        "status": "recording",
        "start_time": time.time(),
        "mac_address": mac_address
    }

    print(f"🤖 Robot {mac_address} started recording - Session: {session_id}", flush=True)
    write_status({
        "source": "robot",
        "session_id": session_id,
        "stage": "robot_recording"
    })

    return {
        "status": "recording_started",
        "session_id": session_id,
        "message": "Robot recording session initiated"
    }

@app.post("/robot/upload-audio")
async def robot_upload_audio(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    doctor_id: Optional[str] = Header(None),
    mac_address: Optional[str] = Header(None, alias="X-Robot-MAC"),
    api_key: Optional[str] = Header(None, alias="X-Robot-API-Key"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not verify_robot(mac_address, api_key):
        raise HTTPException(status_code=403, detail="Unauthorized robot device")

    if not doctor_id:
        raise HTTPException(status_code=400, detail="Doctor ID required")

    uid = uuid.uuid4().hex
    name = f"{uid}_robot_{mac_address.replace(':', '')}_{file.filename}"
    raw = os.path.join(UPLOAD_DIR, name)

    with open(raw, "wb") as f:
        shutil.copyfileobj(file.file, f)

    print(f"🤖 Robot {mac_address} uploaded: {file.filename}", flush=True)

    if session_id and session_id in robot_sessions:
        robot_sessions[session_id]["status"] = "uploaded"
        robot_sessions[session_id]["filename"] = name

    base = os.path.splitext(name)[0]
    wav = os.path.join(PROCESSED_DIR, f"{base}.wav")

    preprocess_audio(raw, wav)
    background_tasks.add_task(process_audio_pipeline, wav, base, "robot", doctor_id)

    return {
        "status": "processing",
        "audio_name": base,
        "session_id": session_id,
        "message": "Robot audio received and processing started"
    }

@app.get("/robot/session/{session_id}")
async def get_robot_session(session_id: str):
    if session_id not in robot_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return robot_sessions[session_id]

# ================= PHONE UPLOAD =================

@app.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    doctor_id: str = Header(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not doctor_id:
        raise HTTPException(status_code=400, detail="Doctor ID missing")

    uid = uuid.uuid4().hex
    name = f"{uid}_phone_{file.filename}"
    raw = os.path.join(UPLOAD_DIR, name)

    with open(raw, "wb") as f:
        shutil.copyfileobj(file.file, f)

    base = os.path.splitext(name)[0]
    wav = os.path.join(PROCESSED_DIR, f"{base}.wav")

    preprocess_audio(raw, wav)
    background_tasks.add_task(process_audio_pipeline, wav, base, "phone_mic", doctor_id)

    return {"status": "processing", "audio_name": base}

# ================= PDF DOWNLOAD =================

@app.get("/download-pdf/{audio_name}")
def download_pdf(audio_name: str):
    path = os.path.join(PDFS_DIR, f"{audio_name}_summary.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{audio_name}.pdf")

# ================= HEALTH CHECK =================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "robot_mac": ALLOWED_ROBOT_MAC,
        "endpoints": {
            "phone_upload": "/upload-audio",
            "robot_start": "/robot/start-recording",
            "robot_upload": "/robot/upload-audio"
        }
    }

# ================= STARTUP =================

@app.on_event("startup")
async def on_startup():
    write_status({"stage": "idle"})
    print("✅ Backend ready!", flush=True)
    print(f"📱 Phone uploads: POST /upload-audio", flush=True)
    print(f"🤖 Robot API: POST /robot/upload-audio", flush=True)
    print(f"🔒 Allowed Robot MAC: {ALLOWED_ROBOT_MAC}", flush=True)
