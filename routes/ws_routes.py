import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from main import process_message
from typing import Set

router = APIRouter()

# Track connected clients
connected_clients: Set[WebSocket] = set()

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 20

# Max messages allowed per second per client
MAX_MESSAGES_PER_SECOND = 5

# Queue size limit
MAX_QUEUE_SIZE = 50

async def heartbeat(websocket: WebSocket):
    """Send a ping to the client every HEARTBEAT_INTERVAL seconds to keep connection alive."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping"})
    except Exception:
        pass  # Exit heartbeat if the connection is closed

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connected")
    connected_clients.add(websocket)

    heartbeat_task = asyncio.create_task(heartbeat(websocket))

    # Rate limiting: track timestamps of received messages
    message_timestamps = []

    # Optional message queue to smooth bursts
    message_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

    async def process_queue():
        """Consume messages from the queue and call process_message."""
        while True:
            msg_type, payload = await message_queue.get()
            try:
                await process_message(websocket, msg_type, payload)
            except Exception as e:
                print(f"❌ Error processing message: {e}")
            finally:
                message_queue.task_done()

    queue_task = asyncio.create_task(process_queue())

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except Exception as e:
                print(f"⚠️ Invalid JSON received: {e}")
                continue

            # Rate limiting
            now = asyncio.get_event_loop().time()
            message_timestamps = [t for t in message_timestamps if now - t < 1]
            if len(message_timestamps) >= MAX_MESSAGES_PER_SECOND:
                print("⚠️ Rate limit exceeded, dropping message")
                continue
            message_timestamps.append(now)

            msg_type = data.get("type")
            payload = data.get("payload", "")
            print(f"[DEBUG] Payload length: {len(payload)}")

            # Put message in queue (drops if full)
            try:
                message_queue.put_nowait((msg_type, payload))
            except asyncio.QueueFull:
                print("⚠️ Message queue full, dropping message")

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        connected_clients.discard(websocket)
        heartbeat_task.cancel()
        queue_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        try:
            await queue_task
        except asyncio.CancelledError:
            pass
