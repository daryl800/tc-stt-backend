import base64
import json
import os
import traceback
import tempfile
import ffmpeg
import shutil
from fastapi import File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
from classify import classify_text
from dateutil import parser as date_parser  # pip install python-dateutil
from extract_event import extract_event_info
from routes.memory_routes import save_memory  # assuming you placed the function here



if shutil.which("ffmpeg") is None:
    raise EnvironmentError("ffmpeg is not installed or not in PATH")


TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

if not TENCENT_SECRET_ID or not TENCENT_SECRET_KEY:
    print("[ERROR] Tencent Cloud credentials are not set.")
else:
    print("[INFO] Tencent Cloud credentials loaded.")


def convert_webm_to_wav(webm_bytes: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as webm_file:
        webm_file.write(webm_bytes)
        webm_path = webm_file.name

    wav_path = webm_path.replace(".webm", ".wav")

    try:
        ffmpeg.input(webm_path).output(wav_path).run(overwrite_output=True, quiet=True)
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
    finally:
        os.remove(webm_path)
        os.remove(wav_path)

    return wav_bytes

async def transcribe_sync(audio: UploadFile = File(...)):
    try:
        print(f"[INFO] Received file: {audio.filename}")
        audio_bytes = await audio.read()
        voice_format = audio.filename.split(".")[-1].lower()
        print(f"[INFO] Detected audio format: {voice_format}")

        # Convert webm to wav if needed
        if voice_format == "webm":
            print("[INFO] Converting webm to wav...")
            audio_bytes = convert_webm_to_wav(audio_bytes)
            voice_format = "wav"

        # Encode audio to base64
        audio_base64 = base64.b64encode(audio_bytes).decode()

        # Tencent ASR
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")
        req = models.SentenceRecognitionRequest()

        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-PY",
            "SourceType": 1,
            "VoiceFormat": voice_format,
            "UsrAudioKey": "test-key",
            "Data": audio_base64,
        }

        print("[INFO] Sending transcription request to Tencent Cloud...")
        req.from_json_string(json.dumps(params))
        resp = client.SentenceRecognition(req)

        transcription = resp.Result
        # ✅ Step: Call classify_memory with the transcribed text
        category = classify_text(transcription)

        print(f"[INFO] Transcription result: {transcription}")
        print(f"[INFO] Classified category: {category}")

        extraction = extract_event_info(transcription)
        print(f"[INFO] extracted info: {extraction}")

        # ✅ Save the memory with transcription and category
        save_memory(extraction)
        # ✅ Return both transcription and category
        return extraction

    except Exception as e:
        print("[ERROR] Transcription failed:")
        traceback.print_exc()
        return {"error": str(e)}
