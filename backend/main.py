from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from language_service import translate_text

import os
import shutil
import json
import uuid
import threading
import time
from dotenv import load_dotenv
from pydub import AudioSegment
from typing import Set

# ================= LOAD ENV =================
load_dotenv()

# ================= FFMPEG =================
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\ffmpeg\bin\ffprobe.exe"

os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"
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

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")
SUMMARIES_DIR = os.path.join(BASE_DIR, "summaries")
PDFS_DIR = os.path.join(BASE_DIR, "pdfs")

BLUETOOTH_DIR = r"C:\Users\AARYA\Downloads\Bluetooth"

STATUS_FILE = os.path.join(BASE_DIR, "status.json")
PROCESSED_LOG = os.path.join(BASE_DIR, "processed_bluetooth.json")

for d in [UPLOAD_DIR, PROCESSED_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR, PDFS_DIR]:
    os.makedirs(d, exist_ok=True)

# ================= GLOBAL LOCK =================
PIPELINE_LOCK = threading.Lock()

# ================= STATUS =================
def write_status(data: dict):
    data["timestamp"] = int(time.time())
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.get("/status")
def get_status():
    if not os.path.exists(STATUS_FILE):
        return {"stage": "idle"}
    with open(STATUS_FILE, encoding="utf-8") as f:
        return json.load(f)

# ================= PROCESSED LOG =================
def load_processed() -> Set[str]:
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
        return set(json.load(f))

def save_processed(p: Set[str]):
    with open(PROCESSED_LOG, "w", encoding="utf-8") as f:
        json.dump(sorted(list(p)), f, indent=2)

# ================= FILE READY CHECK =================
def wait_until_ready(path: str, timeout=20) -> bool:
    last_size = -1
    start = time.time()
    while time.time() - start < timeout:
        try:
            size = os.path.getsize(path)
            if size > 0 and size == last_size:
                return True
            last_size = size
        except FileNotFoundError:
            pass
        time.sleep(0.5)
    return False

# ================= AUDIO PREPROCESS =================
def preprocess_audio(input_path: str, output_wav: str):
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

    lines = []
    for u in utterances:
        role = "Doctor" if u["speaker"] == doctor_speaker else "Patient"
        lines.append(f"{role}: {u['text']}")

    return "\n".join(lines)

def detect_language_from_text(text: str) -> str:
    """
    Detect Hindi by checking for Devanagari characters.
    """
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return "hi"
    return "en"



# ================= CORE PIPELINE =================
def process_audio_pipeline(wav_path: str, base_name: str, source: str):
    with PIPELINE_LOCK:
        try:
            # ================= STATUS: TRANSCRIBING =================
            write_status({
                "source": source,
                "file": base_name,
                "stage": "transcribing"
            })

            # ================= TRANSCRIPTION WITH RETRY =================
            transcript = None
            for _ in range(2):
                transcript = transcribe_audio(wav_path)
                if transcript and getattr(transcript, "text", None):
                    break
                time.sleep(2)

            if not transcript or not transcript.text or not transcript.text.strip():
                raise RuntimeError("Transcription failed or empty")

            # ================= LANGUAGE DETECTION =================
            # AssemblyAI is unreliable for Hinglish → detect from text
            language = detect_language_from_text(transcript.text)  # 🔥 FINAL FIX

            # ================= UTTERANCES =================
            utterances = [
                {
                    "speaker": u.speaker,
                    "text": u.text,
                    "start_ms": u.start,
                    "end_ms": u.end
                }
                for u in (getattr(transcript, "utterances", None) or [])
            ]

            # ================= ROLE-BASED TEXT =================
            role_based_text = format_role_based_text(utterances)

            # ================= TRANSCRIPT JSON =================
            transcript_json = {
                "audio_file": base_name,
                "language": language,          # 🔥 hi / en correctly set
                "full_text": role_based_text,  # 🔥 Doctor / Patient separated
                "utterances": utterances
            }

            # ================= SAVE TRANSCRIPT =================
            tpath = os.path.join(TRANSCRIPTS_DIR, f"{base_name}.json")
            with open(tpath, "w", encoding="utf-8") as f:
                json.dump(transcript_json, f, indent=2, ensure_ascii=False)

            # ================= STATUS: SUMMARIZING =================
            write_status({
                "source": source,
                "file": base_name,
                "language": language,
                "stage": "summarizing"
            })

            # ================= SUMMARY =================
            summary_en = generate_summary(transcript_json)
            if not summary_en:
                raise RuntimeError("Summary generation failed")

            # ================= TRANSLATION (IF HINDI) =================
            if language != "en":
                summary_final = {
                    k: [translate_text(i, language) for i in v]
                    if isinstance(v, list)
                    else translate_text(v, language)
                    for k, v in summary_en.items()
                }
            else:
                summary_final = summary_en

            # ================= SAVE SUMMARY =================
            spath = os.path.join(SUMMARIES_DIR, f"{base_name}_summary.json")
            with open(spath, "w", encoding="utf-8") as f:
                json.dump(summary_final, f, indent=2, ensure_ascii=False)

            # ================= STATUS: PDF =================
            write_status({
                "source": source,
                "file": base_name,
                "language": language,
                "stage": "generating_pdf"
            })

            generate_pdf(spath, language=language)

            # ================= STATUS: COMPLETED =================
            write_status({
                "source": source,
                "file": base_name,
                "language": language,
                "stage": "completed"
            })

            print(f"✅ Pipeline completed → {base_name}")
            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            write_status({
                "source": source,
                "file": base_name,
                "stage": "error",
                "error": str(e)
            })
            return False

# ================= BLUETOOTH WATCHER =================
def bluetooth_watcher():
    print("📡 Bluetooth watcher running", flush=True)
    processed = load_processed()

    while True:
        try:
            if not os.path.exists(BLUETOOTH_DIR):
                time.sleep(3)
                continue

            for file in os.listdir(BLUETOOTH_DIR):
                if file in processed:
                    continue

                if not file.lower().endswith((".wav", ".mp3", ".m4a", ".aac", ".ogg", ".3gp")):
                    continue

                src = os.path.join(BLUETOOTH_DIR, file)
                if not wait_until_ready(src):
                    continue

                uid = uuid.uuid4().hex
                new_name = f"{uid}_{file}"
                upload_path = os.path.join(UPLOAD_DIR, new_name)

                shutil.move(src, upload_path)

                base = os.path.splitext(new_name)[0]
                wav_path = os.path.join(PROCESSED_DIR, f"{base}.wav")

                preprocess_audio(upload_path, wav_path)

                if process_audio_pipeline(wav_path, base, "bluetooth"):
                    processed.add(file)
                    save_processed(processed)

        except Exception:
            import traceback
            traceback.print_exc()

        time.sleep(3)

# ================= WEB UPLOAD =================
@app.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    uid = uuid.uuid4().hex
    name = f"{uid}_{file.filename}"
    raw = os.path.join(UPLOAD_DIR, name)

    with open(raw, "wb") as f:
        shutil.copyfileobj(file.file, f)

    base = os.path.splitext(name)[0]
    wav = os.path.join(PROCESSED_DIR, f"{base}.wav")

    preprocess_audio(raw, wav)

    background_tasks.add_task(process_audio_pipeline, wav, base, "web")
    return {"status": "processing", "audio_name": base}

# ================= PDF DOWNLOAD =================
@app.get("/download-pdf/{audio_name}")
def download_pdf(audio_name: str):
    path = os.path.join(PDFS_DIR, f"{audio_name}_summary.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="application/pdf")

# ================= STARTUP =================
@app.on_event("startup")
def on_startup():
    write_status({"stage": "idle"})
    print("🚀 Starting Bluetooth watcher thread", flush=True)
    threading.Thread(target=bluetooth_watcher, daemon=True).start()
