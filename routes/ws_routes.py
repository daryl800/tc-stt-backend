from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import base64
import uuid

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connected")

    try:
        while True:
            data = await websocket.receive_json()
            print("📥 Received:", data)

            msg_type = data.get("type")
            payload = data.get("payload")

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
            audio_bytes = base64.b64decode(payload)
            # TODO: convert to WAV if needed, then transcribe
            transcription = await dummy_transcribe(audio_bytes)
        elif msg_type == "text":
            transcription = payload.strip()
        else:
            await websocket.send_json({
                "type": "error",
                "message": "Unsupported message type."
            })
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


# --- Dummy placeholder for transcription
async def dummy_transcribe(audio_bytes):
    await asyncio.sleep(1)
    return "我啱啱講過想去澳門玩～"


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
