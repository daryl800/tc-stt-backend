import io
import os
import json
import base64
import asyncio
import traceback
import tempfile
import uuid
import ffmpeg # using ffmpeg to convert .webm audio to .wav
import shutil
from pydub import AudioSegment
from dateutil import parser
from datetime import datetime
import time
from fastapi import File, UploadFile
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models as asr_models
from tencentcloud.tts.v20190823 import tts_client, models as tts_models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from llm_utils import extract_info_withLLM, generate_reflection
from utils.save_memory import save_to_leancloud_async  # assuming you placed the function here
from utils.query_memory import search_past_events  # assuming you placed the function here

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
        # ffmpeg.input(webm_path).output(wav_path).run(overwrite_output=True, quiet=True)
        ffmpeg.input(webm_path).output(wav_path, format='wav', acodec='pcm_s16le').run(overwrite_output=True, quiet=True)

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

    client = get_tts_client()
    # Request and save
    req = tts_models.TextToVoiceRequest()  # ✅ This is the correct class for TTS generation
    req.from_json_string(str(params).replace("'", '"'))  # Convert dict to JSON string

    try:
        resp = client.TextToVoice(req)
        audio_bytes = base64.b64decode(resp.Audio)
        
        print(f"[INFO] Size of data being sent to TC TTS: {len(audio_bytes)/1024:.2f} KB")
        return audio_bytes

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if "PkgExhausted" in str(e):
            print("Solution: Purchase ")

import re

def clean_text(text):
    # Remove control characters except \n
    return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)

def group_segments_by_limit(segments, max_chars=200):
    chunks = []
    current_chunk = ""

    for seg in segments:
        seg = clean_text(seg)
        if len(current_chunk) + len(seg) <= max_chars:
            current_chunk += seg
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(seg) > max_chars:
                # Force-split long segments
                for i in range(0, len(seg), max_chars):
                    chunks.append(seg[i:i+max_chars])
                current_chunk = ""
            else:
                current_chunk = seg

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def extract_info_with_timing(transcription):
    import time
    start = time.time()
    result = extract_info_withLLM(transcription)
    print("[DEBUG] LLM extraction took", round(time.time() - start, 2), "seconds")
    return result

def generate_reflection_with_timing(transcription):
    import time
    start = time.time()
    result = generate_reflection(transcription)
    print("[DEBUG] LLM generate_reflection took", round(time.time() - start, 2), "seconds")
    return result

async def transcribe_sync(filename: str, audio_bytes: bytes):
    try:
        print(f"[INFO] Process begins ...")
        process_start = time.time()
        print(f"[INFO] Received voice file: {filename}")
        voice_format = filename.split(".")[-1].lower()

        # Convert to WAV if needed
        if voice_format == "webm":
            print("[INFO] Converting webm to wav...")
            raw_voice_wav = convert_webm_to_wav(audio_bytes)
            voice_format = "wav"
        else:
            raw_voice_wav = audio_bytes  # already WAV

        # ✅ Now call Tencent ASR client — only after we know we have valid input
        client = get_asr_client()

        # Encode for Tencent ASR
        audio_base64 = base64.b64encode(raw_voice_wav).decode()

        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-PY",  # or "16k_zh-CN" for Cantonese
            "SourceType": 1,
            "VoiceFormat": voice_format,
            "UsrAudioKey": str(uuid.uuid4()),
            "Data": audio_base64,
        }

        print("[INFO] Sending transcription request to Tencent Cloud...")
        req = asr_models.SentenceRecognitionRequest()
        req.from_json_string(json.dumps(params))  
        resp = client.SentenceRecognition(req)
        transcription = resp.Result
        print(f"[INFO] Transcription result: {transcription}")

        # Parallelize TTS + LLM using asyncio.to_thread (since all 3 are sync)
        # tts_task = asyncio.to_thread(tencent_tts, transcription)
        extract_task = asyncio.to_thread(extract_info_with_timing, transcription)
        reflection_task = asyncio.to_thread(generate_reflection_with_timing, transcription)

        try:
            # Wait for all in parallel
            # tts_bytes, extraction, reflection = await asyncio.gather(tts_task, extract_task, reflection_task)
            # if not tts_bytes or len(tts_bytes) < 100:  # sanity threshold
            #     raise ValueError("Empty or invalid TTS audio received.")

            # tts_wav = base64.b64encode(tts_bytes).decode()

            extraction, reflection = await asyncio.gather(extract_task, reflection_task)

        except Exception as e:
            print(f"[ERROR] TTS or extraction failed: {e}")
            tts_wav = base64.b64encode(tencent_tts("出错喇，请稍后再试。")).decode()

        try:
            # 1) Save to DB IMMEDIATELY (without ttsOutput)
            extraction_for_db = extraction.copy()  # Create a clean copy
            if hasattr(extraction_for_db, 'ttsOutput'):
                del extraction_for_db.ttsOutput  # Ensure no ttsOutput in DB version
            
            # Fire-and-forget the DB save (don't await to return faster)
            print("[INFO] Start saving to memory ...")
            asyncio.create_task(
                save_to_leancloud_async(extraction_for_db, raw_voice_wav)
            )

        except Exception as e:
            print(f"[ERROR] Failed to save to LeanCloud: {e}")





        # # Add TTS WAV to be returned to the FE 
        # extraction.ttsOutput = tts_wav

        if extraction.isQuestion:
            try:
                answer = search_past_events(extraction)  # Always returns a list
                segments = []

                # Loop through all results (works even if answer == [])
                for item in answer:  # No need for isinstance(answer, list)
                    raw_date = item.get('eventCreatedAt', '')
                    try:
                        if isinstance(raw_date, datetime):
                            dt = raw_date
                        else:
                            dt = parser.isoparse(raw_date)
                        formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception as e:
                        formatted_date = str(raw_date)

                    event = item.get('transcription', '')
                    segments.append(f"你系 {formatted_date} 讲过: {event}")

                    if segments:  # If any matches found
                        combined = AudioSegment.empty()
                        tts_chunks = group_segments_by_limit(segments)
                        
                        for chunk in tts_chunks:
                            tts_audio_bytes = tencent_tts(chunk)
                            audio_segment = AudioSegment.from_file(io.BytesIO(tts_audio_bytes), format="wav")
                            combined += audio_segment

                        buf = io.BytesIO()
                        combined.export(buf, format="wav")
                        tts_wav = base64.b64encode(buf.getvalue()).decode()

                    else:  # No matches found
                        tts_wav = base64.b64encode(tencent_tts("你之前好似冇提过关于 " 
                                                            + answer.get('eventCreatedAt'), 
                                                            + "既内容。不过，我揾到以下的资料，你可以参考下。" 
                                                            + reflection )).decode()
            except Exception as e:
                print("[ERROR] TTS for question failed:")
                traceback.print_exc()
                try:
                    tts_wav = base64.b64encode(tencent_tts("出错喇，请稍后再试。")).decode()
                except:
                    tts_wav = ""
        else:
            tts_wav = base64.b64encode(tencent_tts("已经记低左 " + transcription )).decode()

        # Set final TTS output
        extraction.ttsOutput = tts_wav

        # Remove non-serializable fields (original raw_wav)
        extraction_dict = extraction.dict(exclude={"originalVoice_Url"}, exclude_unset=True)


        # ➕ Attach reflection to response but not database
        # extraction_dict["reflection"] = reflection

        # Return the processed data as a clean dictionary
        print("[DEBUG] Total response size (bytes):", len(json.dumps(extraction_dict)))
        print("[DEBUG] Full transcription cycle took", round(time.time() - process_start, 2), "seconds")


        return extraction_dict
        
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        traceback.print_exc()
        return {"error": str(e), "message": "An error occurred during transcription."}
    