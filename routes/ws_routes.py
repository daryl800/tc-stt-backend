import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from main import process_message  # your existing processing function

router = APIRouter()

# Async queue to handle incoming messages
message_queue: asyncio.Queue[tuple[WebSocket, str, str]] = asyncio.Queue(maxsize=50)


async def process_queue():
    """Background task to process queued messages."""
    while True:
        try:
            websocket, msg_type, payload = await message_queue.get()
            # Only process if websocket is still connected
            if websocket.client_state.value == 1:  # CONNECTED
                await process_message(websocket, msg_type, payload)
        except Exception as e:
            print(f"❌ Error processing queued message: {e}")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connected")

    # Start background queue processor
    queue_task = asyncio.create_task(process_queue())

    try:
        while True:
            try:
                data = await websocket.receive_json()
                print("📥 Received data type:", data.get("type"))
            except WebSocketDisconnect:
                print("❌ WebSocket disconnected")
                break
            except Exception as e:
                print(f"⚠️ Invalid JSON received: {e}")
                continue

            msg_type = data.get("type")
            payload = data.get("payload", "")
            try:
                message_queue.put_nowait((websocket, msg_type, payload))
            except asyncio.QueueFull:
                print("⚠️ Message queue full, dropping message")

    finally:
        # Cleanup
        queue_task.cancel()
        try:
            await queue_task
        except asyncio.CancelledError:
            pass
        print("🛑 WebSocket cleanup finished")
