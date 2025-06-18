# utils/transcription.py

import ffmpeg
import base64
import uuid
import sys
import os
import json
from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

from pydub import AudioSegment
import asyncio

# Add parent directory of utils
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY

# Setup credentials
cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)

# Initialize Hunyuan client (singleton pattern)
def get_asr_client():
    return  asr_client.AsrClient(cred, "ap-guangzhou")


async def base64_to_wav_path(audio_base64: str) -> str:
    webm_data = base64.b64decode(audio_base64)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as webm_file:
        webm_file.write(webm_data)
        webm_path = webm_file.name

    wav_path = webm_path.replace(".webm", ".wav")

    # ✅ Convert using ffmpeg with proper format and codec
    ffmpeg.input(webm_path).output(
        wav_path, format='wav', acodec='pcm_s16le'
    ).run(overwrite_output=True, quiet=True)

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
            "EngSerViceType": "16k_zh-PY",  # or "16k_zh-CN" for Cantonese
            "SourceType": 1,
            "VoiceFormat": "wav",
            "UsrAudioKey": str(uuid.uuid4()),
            "Data": base64.b64encode(audio_data).decode("utf-8"),
        }
        req.from_json_string(json.dumps(params))
        print("[INFO] Sending transcription request to Tencent ASR...")
        resp = await asyncio.to_thread(client.SentenceRecognition, req)
        print(f"[INFO] Transcription result: {resp.Result}")

        return resp.Result

    except TencentCloudSDKException as e:
        return f"[Tencent ASR Error] {str(e)}"
