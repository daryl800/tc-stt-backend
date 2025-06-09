import base64
import json
import os
import traceback
import tempfile
import ffmpeg # using ffmpeg to convert .webm audio to .wav
import shutil
from fastapi import File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from classify import classify_text
from dateutil import parser as date_parser  # pip install python-dateutil
from extract_event import extract_event_info
from utils.save_memory import save_to_leancloud  # assuming you placed the function here
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models as asr_models
from tencentcloud.tts.v20190823 import tts_client, models as tts_models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
import base64
from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY

if shutil.which("ffmpeg") is None:
    raise EnvironmentError("ffmpeg is not installed or not in PATH")

# Setup credentials
cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)

# Initialize Hunyuan client (singleton pattern)
def get_asr_client():
    return  asr_client.AsrClient(cred, "ap-guangzhou")

def get_tts_client():
    return tts_client.TtsClient(cred, "ap-guangzhou") 


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


def tencent_tts(text):
    # Request setup (CORRECT: Using TextToVoiceRequest)
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

    req = tts_models.TextToVoiceRequest()  # ✅ This is the correct class for TTS generation
    req.from_json_string(str(params).replace("'", '"'))  # Convert dict to JSON string

    client = get_tts_client()
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

        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-PY",  # or "16k_zh-CN" for Cantonese
            "SourceType": 1,
            "VoiceFormat": voice_format,
            "UsrAudioKey": "test-key",
            "Data": audio_base64,
        }

        print("[INFO] Sending transcription request to Tencent Cloud...")
        req = asr_models.SentenceRecognitionRequest()
        req.from_json_string(json.dumps(params))

        client = get_asr_client()
        resp = client.SentenceRecognition(req)

        transcription = resp.Result
        tts_wav = base64.b64encode(tencent_tts(transcription)).decode()

        # Extract event info
        extraction = extract_event_info(transcription)

        print(f"[INFO] Transcription result: {transcription}")
        print(f"[INFO] Extracted info: {extraction}")

        # Add the raw_wav and text fields to the extraction
        extraction.raw_wav = raw_wav  # This will be handled for LeanCloud file upload
        extraction.text = transcription  # Ensure transcription text is set

        # Save the data to LeanCloud
        save_to_leancloud(extraction)  # This function will now handle saving audio as well
        print("[INFO] Memory saved successfully.")

        # Add TTS WAV for future reference (make sure LeanCloud can handle this)
        extraction.tts_wav = tts_wav

        # Clean up non-serializable fields (raw_wav, if necessary)
        extraction_dict = extraction.dict(exclude={"raw_wav"}, exclude_unset=True)

        # Return the processed data as a clean dictionary
        return extraction_dict

    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return {"error": str(e), "message": "An error occurred during transcription."}


    except Exception as e:
        print("[ERROR] Transcription failed:")
        traceback.print_exc()
        return {"error": str(e)}
