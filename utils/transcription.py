# utils/transcription.py

from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY
import sys
import os
import uuid
import json
import shutil
import ffmpeg
import base64
import wave
import tempfile
from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

from pydub import AudioSegment
import asyncio

# Add parent directory of utils
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Setup credentials
cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)

if shutil.which("ffmpeg") is None:
    raise EnvironmentError("ffmpeg is not installed or not in PATH")

# Initialize Hunyuan client (singleton pattern)


def get_asr_client():
    return asr_client.AsrClient(cred, "ap-hongkong")


async def webm_bytes_to_wav_path(webm_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as webm_file:
        webm_file.write(webm_bytes)  # write the webm bytes into a file
        webm_path = webm_file.name

    wav_path = webm_path.replace(".webm", ".wav")

    try:
        ffmpeg.input(webm_path).output(
            wav_path, format='wav', acodec='pcm_s16le'
        ).run(overwrite_output=True, quiet=True)

        # ✅ Check if wav file exists and is non-empty
        if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
            raise RuntimeError("Converted WAV file is missing or empty")

        # ✅ (Optional) Verify it's a valid WAV file
        with wave.open(wav_path, 'rb') as wav_file:
            wav_file.getparams()  # This will raise if file is invalid

    finally:
        os.remove(webm_path)

    return wav_path


async def transcribe_tencent(wav_path: str) -> str:
    try:
        client = get_asr_client()

        with open(wav_path, "rb") as f:
            audio_data = f.read()

        req = models.SentenceRecognitionRequest()
        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-TW",  
            "SourceType": 1,
            "VoiceFormat": "wav",
            "UsrAudioKey": str(uuid.uuid4()),
            "Data": base64.b64encode(audio_data).decode("utf-8"),
        }
        req.from_json_string(json.dumps(params))
        print("[INFO] Sending transcription request to Tencent ASR...")
        resp = await asyncio.to_thread(client.SentenceRecognition, req)
        print(
            f"[INFO] Transcription result (inside Transcribe_tencent): {resp.Result}")

        return resp.Result

    except TencentCloudSDKException as e:
        return f"[Tencent ASR Error] {str(e)}"


async def transcribe_base64_webm_to_text(audio_base64_webm: str) -> str:
    print("[INFO - transcribe_base64_webm_to_text: ] Converting webm to wav...")
    audio_bytes = base64.b64decode(audio_base64_webm)
    wav_path = await webm_bytes_to_wav_path(audio_bytes)
    result = await transcribe_tencent(wav_path)
    print(
        f"[INFO - transcribe_base64_webm_to_text: ] transcribed result: {result}")
    os.remove(wav_path)
    return result
