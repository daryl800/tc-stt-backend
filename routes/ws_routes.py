import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from main import process_message

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
            reply_to_FE(websocket, "placeholder", "🧠 好喇，等我幫你記住先～")

            # ✅ Step 2.2: Spawn async task
            asyncio.create_task(process_message(websocket, msg_type, payload))

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")

async def reply_to_FE(websocket: WebSocket, msg_type: str, payload: str):
    await websocket.send_json({
        "type":  msg_type,
        "payload": payload
    })