import base64
import json
import os
import traceback
import tempfile
import ffmpeg
import shutil
from fastapi import File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from classify import classify_text
from dateutil import parser as date_parser  # pip install python-dateutil
from extract_event import extract_event_info
from routes.memory_routes import save_memory  # assuming you placed the function here
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models as asr_models
from tencentcloud.tts.v20190823 import tts_client, models as tts_models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
import base64


if shutil.which("ffmpeg") is None:
    raise EnvironmentError("ffmpeg is not installed or not in PATH")

TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")
TENCENT_HUNYUAN_SECRET_ID = os.getenv("TENCENT_HUNYUAN_SECRET_ID")
TENCENT_HUNYUAN_SECRET_KEY = os.getenv("TENCENT_HUNYUAN_SECRET_KEY")

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

# Setup credentials
cred = credential.Credential(TENCENT_HUNYUAN_SECRET_ID, TENCENT_HUNYUAN_SECRET_KEY)
client = tts_client.TtsClient(cred, "ap-guangzhou")  # Adjust region if needed

def tencent_tts(text):
    # Request setup (CORRECT: Using TextToVoiceRequest)
    req = tts_models.TextToVoiceRequest()  # ✅ This is the correct class for TTS generation
    params = {
        "Text": text,
        "SessionId": "test-123",
        "ModelType": 1,
        "VoiceType": 101019,  # Cantonese Female 
        "Codec": "wav",
        "Volume": 5,
        "Speed": 0,
        "ProjectId": 0,
        "SampleRate": 16000
    }
    req.from_json_string(str(params).replace("'", '"'))  # Convert dict to JSON string

    # Request and save
    try:
        resp = client.TextToVoice(req)
        audio_bytes = base64.b64decode(resp.Audio)
        
        print(f"File size: {len(audio_bytes)/1024:.2f} KB")
        return audio_bytes

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if "PkgExhausted" in str(e):
            print("Solution: Purchase ")


async def transcribe_sync(audio: UploadFile = File(...)):
    try:
        print(f"[INFO] Received file: {audio.filename}")
        audio_bytes = await audio.read()
        voice_format = audio.filename.split(".")[-1].lower()
        print(f"[INFO] Detected audio format: {voice_format}")

        # Convert to WAV if needed
        if voice_format == "webm":
            print("[INFO] Converting webm to wav...")
            raw_wav = convert_webm_to_wav(audio_bytes)
            voice_format = "wav"
        else:
            raw_wav = audio_bytes  # already WAV

        # Encode for Tencent ASR
        audio_base64 = base64.b64encode(raw_wav).decode()

        # Tencent ASR request
        cred = credential.Credential(TENCENT_HUNYUAN_SECRET_ID, TENCENT_HUNYUAN_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")
        req = asr_models.SentenceRecognitionRequest()

        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-PY",  # or "16k_zh-CN" if Cantonese
            "SourceType": 1,
            "VoiceFormat": voice_format,
            "UsrAudioKey": "test-key",
            "Data": audio_base64,
        }

        print("[INFO] Sending transcription request to Tencent Cloud...")
        req.from_json_string(json.dumps(params))
        resp = client.SentenceRecognition(req)

        transcription = resp.Result
        tts_wav = base64.b64encode(tencent_tts(transcription)).decode()

        category = classify_text(transcription)
        extraction = extract_event_info(transcription)

        print(f"[INFO] Transcription result: {transcription}")
        print(f"[INFO] Classified category: {category}")
        print(f"[INFO] Extracted info: {extraction}")

        extraction["raw_wav"] = raw_wav  # used later for LeanCloud file upload
        extraction["text"] = transcription
        save_memory(extraction)  # This should handle saving audio too
        print("[INFO] Memory saved successfully.")

        extraction["tts_wav"] = tts_wav
        
        # Clean up non-serializable field
        extraction.pop("raw_wav", None)

        # Now return it safely
        return extraction



    except Exception as e:
        print("[ERROR] Transcription failed:")
        traceback.print_exc()
        return {"error": str(e)}
