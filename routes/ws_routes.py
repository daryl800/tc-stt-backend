
import os
import base64
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.transcription import webm_bytes_to_wav_path, transcribe_tencent

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connected")

    try:
        while True:
            data = await websocket.receive_json()
            print("📥 Received data from websocket")

            msg_type = data.get("type")
            payload = data.get("payload")

            print(f"[DEBUG] Base64 payload length: {len(payload)}")

            # ✅ Step 2.1: Immediately respond with calming placeholder
            await websocket.send_json({
                "type": "placeholder",
                "message": "🧠 好喇，等我幫你記住先～"
            })

            # ✅ Step 2.2: Spawn async task
            asyncio.create_task(process_message(websocket, msg_type, payload))

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")


async def process_message(websocket: WebSocket, msg_type: str, payload: str):
    try:
        # --- Step A: Decode audio or read text
        if msg_type == "audio":
            # In process_message:
            transcription = await transcribe_base64_webm_to_text(payload)  # payload is still base64 string
            print(f"📥 transcription from voice : {transcription}")
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

        # --- Step B: Send transcription as quick confirmation
        await websocket.send_json({
            "type": "transcription",
            "text": transcription
        })

        # --- Step C: Determine if it's a question (about memory)
        is_question = "有冇" in transcription or "提過" in transcription or "講過" in transcription

        if is_question:
            # Simulate search taking 30s — provide insight first
            asyncio.create_task(provide_insight_then_result(websocket, transcription))
        else:
            # Save memory and ask if user wants more info
            await websocket.send_json({
                "type": "saved",
                "message": "✅ 記低咗喇！",
                "ask_more": f"你想唔想我講多啲關於「{transcription}」？"
            })

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

async def transcribe_base64_webm_to_text(audio_base64_webm: str) -> str:
    print("[INFO - transcribe_base64_webm_to_text: ] Converting webm to wav...")
    audio_bytes = base64.b64decode(audio_base64_webm)
    wav_path = await webm_bytes_to_wav_path(audio_bytes)
    result = await transcribe_tencent(wav_path)
    print(f"[INFO - transcribe_base64_webm_to_text: ] transcribed result: {result}")
    os.remove(wav_path)
    return result

async def provide_insight_then_result(websocket: WebSocket, question: str):
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
