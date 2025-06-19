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
from utils.transcription import transcribe_base64_webm_to_text
from utils.llm_utils import extract_info_withLLM, generate_reflection
from utils.db_utils import save_to_leancloud_async
from utils.query_memory import search_past_events  # assuming you placed the function here
from utils.transcription import webm_bytes_to_wav_path, transcribe_tencent

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


async def reply_to_FE(websocket: WebSocket, msg_type: str, payload: str):
    await websocket.send_json({
        "type":  msg_type,
        "payload": payload
    })

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

        # response_tts_wav = base64.b64encode(tencent_tts("✅ 收到你头先講嘅嘢，我而家會幫你處理，麻烦您比少少耐性 ...")).decode()
        # await reply_to_FE(websocket, 'audio', response_tts_wav)

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
        is_query = "有冇" in transcription or "提過" in transcription or "講過" in transcription or "有冇講過" in transcription or  "提及過" in transcription or "提及关于" in transcription

        if is_query:
            response_tts_wav = base64.b64encode(tencent_tts("咁樣你要俾啲耐性我，我而家幫你搵吓你之前有冇講過呢啲嘢啦！" 
                                                            + reflection )).decode()
            await reply_to_FE(websocket, 'audio', response_tts_wav)
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
                    segments.append(f"你曾经系 {formatted_date} 讲过: {event}")

                    if segments:  # If any matches found
                        combined = AudioSegment.empty()
                        tts_chunks = group_segments_by_limit(segments)
                        
                        for chunk in tts_chunks:
                            tts_audio_bytes = tencent_tts(chunk)
                            audio_segment = AudioSegment.from_file(io.BytesIO(tts_audio_bytes), format="wav")
                            combined += audio_segment

                        buf = io.BytesIO()
                        combined.export(buf, format="wav")
                        response_tts_wav = base64.b64encode(buf.getvalue()).decode()

                    else:  # No matches found
                        response_tts_wav = base64.b64encode(tencent_tts("你之前好似冇提过关于 " 
                                                            + "既内容。不过，我揾到以下的资料，你可以参考下。" 
                                                            + reflection )).decode()
                        
            except Exception as e:
                print("[ERROR] TTS for question failed:")
                traceback.print_exc()
                try:
                    response_tts_wav = base64.b64encode(tencent_tts("出错喇，请稍后再试。")).decode()
                except:
                    response_tts_wav = ""  

        else:
            response_tts_wav = base64.b64encode(tencent_tts(reflection)).decode() 
            
        await reply_to_FE(websocket, 'audio', response_tts_wav)

        # if is_query:
        #     # Simulate search taking 30s — provide insight first
        #     asyncio.create_task(provide_insight_then_result(websocket, transcription))
        # else:
        #     # response_tts_wav = base64.b64encode(tencent_tts("✅ 你头先话 " + transcription + ", 我已经帮你记低左啦!")).decode() 
        #     response_tts_wav = base64.b64encode(tencent_tts(reflection)).decode() 
        #     await reply_to_FE(websocket, 'audio', response_tts_wav)

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


async def query_history(websocket: WebSocket, query: str):
    # Step 1: Insight or speculation
    await websocket.send_json({
        "type": "insight",
        "message": "🔍 緊張搜尋中，不過我估你可能係想搵返你之前講過關於澳門嘅野～"
    })

    # Step 2: Simulate slow DB/search (real logic later)
    await asyncio.sleep(6)

    await websocket.send_json({
        "type": "search_result",
        "result": "你上星期三曾經講過『我想去澳門影下夜景』～"
    })
