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
from utils.tencent_tts_short import tencent_tts, group_segments_by_limit
from utils.gorq_websearch_qw_llm import extract_info_withLLM, generate_reflection
from utils.db_utils import save_to_leancloud_async
# assuming you placed the function here
from utils.query_memory import search_past_events
from utils.transcription import webm_bytes_to_wav_path, transcribe_tencent
from utils.comm_utils import reply_to_FE, enqueue_audio
from utils.filler_utils import pick_random_filler
from fastapi.encoders import jsonable_encoder


def extract_info_with_timing(transcription):
    start = time.time()
    result = extract_info_withLLM(transcription)
    print("[DEBUG] LLM extraction took", round(
        time.time() - start, 2), "seconds")
    return result


def generate_reflection_with_timing(transcription):
    start = time.time()
    result = generate_reflection(transcription)
    print("[DEBUG] LLM generate_reflection took",
          round(time.time() - start, 2), "seconds")
    return result


async def transcribe_workflow(base64_audio_str: str):
    audio_bytes = base64.b64decode(base64_audio_str)
    wav_path = await webm_bytes_to_wav_path(audio_bytes)
    with open(wav_path, "rb") as f:
        wav_bytes = f.read()
    transcription = await transcribe_tencent(wav_path)
    os.remove(wav_path)
    return transcription, wav_bytes


async def process_message(websocket: WebSocket, msg_type: str, payload: str):
    try:
        # --- Step A: Decode audio or read text
        if msg_type == "audio":
            # filler_task = asyncio.to_thread(lambda: base64.b64encode(pick_random_filler()).decode())
            transcribe_task = asyncio.create_task(transcribe_workflow(payload))

            # # Send filler audio as soon as ready
            # filler_audio = await filler_task
            # await reply_to_FE(websocket, 'audio', filler_audio)

            # Get transcription and wav bytes
            transcription, wav_bytes = await transcribe_task
        elif msg_type == "text":
            transcription = payload.strip()
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Unsupported message type."
            })
            print(f"📥 Error transcripting!")
            return
        await reply_to_FE(websocket, 'text', "👋，收到 📥 ... 思考中 ⏳ ...")

        # --- Step C: Determine if it's a query (about memory)
        is_query = (
            "有冇" in transcription
            or "提過" in transcription
            or "提过" in transcription
            or "講過" in transcription
            or "讲过" in transcription
            or "談過" in transcription
            or "談及過" in transcription
            or "談過關於" in transcription
            or "有冇講過" in transcription
            or "有冇讲过" in transcription
            or "係咪講過" in transcription
            or "系咪讲过" in transcription
            or "有冇提過" in transcription
            or "有冇提过" in transcription
            or "有冇提及過" in transcription
            or "有冇提及过" in transcription
            or "提及關於" in transcription
            or "提及关于" in transcription
        )

        # Send inital response ASAP if it is a query
        if is_query:
            initial_tts = base64.b64encode(
                tencent_tts("💬等一阵...比少少时间我揾揾🔎～")
            ).decode()
            await reply_to_FE(websocket, 'audio', initial_tts)

        extract_task = asyncio.to_thread(
            extract_info_with_timing, transcription)
        reflection_task = asyncio.to_thread(
            generate_reflection_with_timing, transcription)

        try:
            # 只等 reflection，立刻啟動 TTS
            reflection = await reflection_task
            reflection_tts_task = asyncio.to_thread(tencent_tts, reflection)

            # 這時 extract_task 可能還沒跑完，沒關係
            extraction = await extract_task

        except Exception as e:
            print(f"[ERROR] TTS or extraction failed: {e}")
            # response_tts_wav = base64.b64encode(tencent_tts("出错喇，请稍后再试。")).decode()

        try:
            # Fire-and-forget the DB save (don't await to return faster)
            print(f"[INFO] Saving extraction to leanCloud: {extraction}")
            asyncio.create_task(
                save_to_leancloud_async(extraction, wav_bytes)
            )
        except Exception as e:
            print(f"[ERROR] Failed to save to LeanCloud: {e}")

        if is_query:
            try:
                # Assume this returns a list
                answer = search_past_events(extraction)
                segments = []

                if answer:
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
                    segments.append(f"喺咁多啦～")
                    # Generate and send audio replies sequentially
                    if segments:
                        combined = AudioSegment.empty()
                        tts_chunks = group_segments_by_limit(segments)

                        # for chunk in tts_chunks:
                        #     tts_audio_bytes = tencent_tts(chunk)
                        #     audio_segment = AudioSegment.from_file(io.BytesIO(tts_audio_bytes), format="wav")
                        #     combined += audio_segment

                        # buf = io.BytesIO()
                        # combined.export(buf, format="wav")
                        # accumulated_tts_wav = base64.b64encode(buf.getvalue()).decode()

                        # await enqueue_audio(websocket, accumulated_tts_wav)

                        for chunk in tts_chunks:
                            tts_audio_bytes = await asyncio.to_thread(tencent_tts, chunk)
                            b64_audio = base64.b64encode(
                                tts_audio_bytes).decode()
                            await enqueue_audio(websocket, b64_audio)

                else:
                    no_match_tts = base64.b64encode(
                        tencent_tts("你之前好似冇提过关于" + ", ".join(extraction.tags) +
                                    "嘅嘢!。不过，我揾到以下嘅嘢，你可以参考下。" + reflection)
                    ).decode()
                    await enqueue_audio(websocket, no_match_tts)

            except Exception as e:
                print("[ERROR] TTS for question failed:")
                traceback.print_exc()
                error_tts = base64.b64encode(
                    tencent_tts("出错喇，请稍后再试。")).decode()
                await enqueue_audio(websocket, error_tts)
        else:
            response_dict = jsonable_encoder(extraction)
            response_dict["reflection"] = reflection
            await reply_to_FE(websocket, 'obj', response_dict)
            # Default response for non-query cases
            # Then wait for the TTS result when ready to send
            reflection_tts_bytes = await reflection_tts_task
            reflection_tts_wav = base64.b64encode(
                reflection_tts_bytes).decode()
            print(f"[DEBUG] Sending back reflection in voice ...")
            await enqueue_audio(websocket, reflection_tts_wav)

    except Exception as e:
        print(f"[ERROR] TTS or extraction failed: {e}")
        await reply_to_FE(websocket, "error", f"Extraction or TTS failed: {e}")
        return  # <- STOP execution here
