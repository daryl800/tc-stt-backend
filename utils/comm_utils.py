
import asyncio
from fastapi import WebSocket
from typing import Union


async def reply_to_FE(websocket: WebSocket, msg_type: str, payload: Union[dict, list, int, float, bool]):
    await websocket.send_json({
        "type":  msg_type,
        "payload": payload
    })


audio_queue = asyncio.Queue()
sending_task = None


async def enqueue_audio(websocket: WebSocket, base64_wav: str):
    global sending_task
    await audio_queue.put((websocket, base64_wav))

    if sending_task is None or sending_task.done():
        sending_task = asyncio.create_task(audio_sending_loop())


async def audio_sending_loop():
    while not audio_queue.empty():
        websocket, base64_audio = await audio_queue.get()
        try:
            await reply_to_FE(websocket, 'audio', base64_audio)
            await asyncio.sleep(0.3)  # To avoid overlap
        except Exception as e:
            print(f"[ERROR] Failed to send audio: {e}")
        audio_queue.task_done()
