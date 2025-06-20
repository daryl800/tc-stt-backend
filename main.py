import io
import os
import base64
import asyncio
import time
import traceback
from dateutil import parser
from datetime import datetime
from pydub import AudioSegment
from dateutil import parser
from fastapi import WebSocket
from utils.text_to_speech import tencent_tts, group_segments_by_limit
from utils.llm_utils import extract_info_withLLM, generate_reflection
from utils.db_utils import save_to_leancloud_async
from utils.query_memory import search_past_events  # assuming you placed the function here
from utils.transcription import webm_bytes_to_wav_path, transcribe_tencent
from utils.comm_utils import reply_to_FE, enqueue_audio

def extract_info_with_timing(transcription):
    start = time.time()
    result = extract_info_withLLM(transcription)
    print("[DEBUG] LLM extraction took", round(time.time() - start, 2), "seconds")
    return result

def generate_reflection_with_timing(transcription):
    start = time.time()
    result = generate_reflection(transcription)
    print("[DEBUG] LLM generate_reflection took", round(time.time() - start, 2), "seconds")
    return result


async def process_message(websocket: WebSocket, msg_type: str, payload: str):
    try:
        # --- Step A: Decode audio or read text
        if msg_type == "audio":
            # In process_message:
            # transcription = await transcribe_base64_webm_to_text(payload) 
            # print(f"📥 transcription from voice : {transcription}")

            print("[INFO - transcribe_base64_webm_to_text: ] Converting webm to wav...")
            audio_bytes = base64.b64decode(payload)
            wav_path = await webm_bytes_to_wav_path(audio_bytes)
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()
            transcription = await transcribe_tencent(wav_path)
            print(f"[INFO - transcribe_base64_webm_to_text: ] transcribed result: {transcription}")
            os.remove(wav_path)
        elif msg_type == "text":
            transcription = payload.strip()
            print(f"📥 transcription from text: {transcription}")
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Unsupported message type."
            })
            print(f"📥 Error transcripting!")
            return

        # Parallelize TTS + LLM using asyncio.to_thread (since all 3 are sync)
        tts_task = asyncio.to_thread(tencent_tts, transcription)
        extract_task = asyncio.to_thread(extract_info_with_timing, transcription)
        reflection_task = asyncio.to_thread(generate_reflection_with_timing, transcription)

        try:
            # Wait for all in parallel
            tts_bytes, extraction, reflection = await asyncio.gather(tts_task, extract_task, reflection_task)
            if not tts_bytes or len(tts_bytes) < 100:  # sanity threshold
                raise ValueError("Empty or invalid TTS audio received.")

            response_tts_wav = base64.b64encode(tts_bytes).decode()

        except Exception as e:
            print(f"[ERROR] TTS or extraction failed: {e}")
            response_tts_wav = base64.b64encode(tencent_tts("出错喇，请稍后再试。")).decode()

        try:
            # Fire-and-forget the DB save (don't await to return faster)
            print(f"[INFO] Saving extraction to leanCloud: {extraction}")
            asyncio.create_task(
                save_to_leancloud_async(extraction, wav_bytes)
            )

        except Exception as e:
            print(f"[ERROR] Failed to save to LeanCloud: {e}")


        # --- Step C: Determine if it's a query (about memory)
        is_query = (
            "有冇" in transcription 
            or "提過" in transcription 
            or "講過" in transcription 
            or "有冇講過" in transcription 
            or "有冇提及過" in transcription 
            or "提及关于" in transcription
        )

        if is_query:
            # Initial response (always sent first)
            initial_tts = base64.b64encode(
                tencent_tts("咁你要俾啲耐性我，我而家幫你搵吓你之前有冇提及過关于" + ", ".join(extraction.tags) + "嘅嘢!")
            ).decode()
            # await enqueue_audio(websocket, initial_tts)
            await reply_to_FE(websocket, 'audio', initial_tts)

            try:
                answer = search_past_events(extraction)  # Assume this returns a list
                segments = []

                # Process all items first
                for item in answer:
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
                    segments.append(f"你曾经系 {formatted_date} 讲过: {event}")

                # Generate and send audio replies sequentially
                if segments:
                    combined = AudioSegment.empty()
                    tts_chunks = group_segments_by_limit(segments)
                    
                    for chunk in tts_chunks:
                        tts_audio_bytes = tencent_tts(chunk)
                        audio_segment = AudioSegment.from_file(io.BytesIO(tts_audio_bytes), format="wav")
                        combined += audio_segment

                    buf = io.BytesIO()
                    combined.export(buf, format="wav")
                    accumulated_tts_wav = base64.b64encode(buf.getvalue()).decode()
                    
                    await enqueue_audio(websocket, accumulated_tts_wav)
                else:
                    no_match_tts = base64.b64encode(
                        tencent_tts("你之前好似冇提过关于呢啲内容。不过，我揾到以下的资料，你可以参考下。" + reflection)
                    ).decode()
                    await enqueue_audio(websocket, no_match_tts)

            except Exception as e:
                print("[ERROR] TTS for question failed:")
                traceback.print_exc()
                error_tts = base64.b64encode(tencent_tts("出错喇，请稍后再试。")).decode()
                await enqueue_audio(websocket, error_tts)

        else:
            # Default response for non-query cases
            reflection_tts_wav = base64.b64encode(tencent_tts(reflection)).decode()
            await enqueue_audio(websocket, reflection_tts_wav)


    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
