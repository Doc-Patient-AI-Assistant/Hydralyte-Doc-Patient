import assemblyai as aai
import os
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()

ASSEMBLY_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not ASSEMBLY_API_KEY:
    raise RuntimeError(
        "ASSEMBLYAI_API_KEY not set. Add it to your .env file."
    )

aai.settings.api_key = ASSEMBLY_API_KEY


# ================= TRANSCRIPTION =================
def transcribe_audio(audio_path: str):
    print("📤 AssemblyAI: preparing transcription")
    print(f"🎧 Audio path: {audio_path}")

    # 🔥 CRITICAL CONFIG FOR YOUR USE CASE
    config = aai.TranscriptionConfig(
        speaker_labels=True,        # REQUIRED for doctor/patient split
        speakers_expected=2,        # Doctor + Patient
        language_detection=True,    # Auto EN / HI
        punctuate=True,
        format_text=True,
        disfluencies=False          # Cleaner medical text
    )

    transcriber = aai.Transcriber()

    print("⏳ AssemblyAI: uploading & transcribing (this may take time)...")
    transcript = transcriber.transcribe(audio_path, config)

    # ================= ERROR HANDLING =================
    if transcript.status == aai.TranscriptStatus.error:
        print("❌ AssemblyAI error:", transcript.error)
        raise RuntimeError(transcript.error)

    print("✅ AssemblyAI transcription completed")

    # ================= DEBUG LOGS =================
    # Language (may or may not exist depending on SDK/version)
    if hasattr(transcript, "language") and transcript.language:
        print(f"🗣 AssemblyAI detected language: {transcript.language}")
    elif hasattr(transcript, "language_code") and transcript.language_code:
        print(f"🗣 AssemblyAI detected language: {transcript.language_code}")
    else:
        print("⚠️ AssemblyAI language not returned")

    # Speaker diarization check
    if hasattr(transcript, "utterances") and transcript.utterances:
        speakers = {u.speaker for u in transcript.utterances}
        print(f"🧑‍⚕️ Speakers detected: {', '.join(sorted(speakers))}")
        print(f"🗣 Utterances count: {len(transcript.utterances)}")
    else:
        print("⚠️ No utterances returned (speaker_labels may have failed)")

    # Transcript length
    if transcript.text:
        print(f"📝 Transcript length: {len(transcript.text)} characters")
    else:
        print("⚠️ Empty transcript received")

    return transcript
