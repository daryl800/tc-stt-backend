import asyncio
import json
import time
from typing import Union
from collections import deque
from utils.log import logger
from fastapi import WebSocket

VOICETYPE = 101019  # Cantonese Female
FASTVOICETYPE = ""
CODEC = "pcm"  # 音频格式：pcm/mp3
SAMPLE_RATE = 16000  # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

async def reply_to_FE(websocket: WebSocket, msg_type: str, payload: Union[dict, list, int, float, bool]):
    await websocket.send_json({
        "type":  msg_type,
        "payload": payload
    })

audio_queue = asyncio.Queue()
sending_task = None
