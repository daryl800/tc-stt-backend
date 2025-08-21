import asyncio
import json
import time
from typing import Union
from collections import deque
from utils.log import logger
from fastapi import WebSocket

async def reply_to_FE(websocket: WebSocket, msg_type: str, payload: Union[dict, list, int, float, bool]):
    await websocket.send_json({
        "type":  msg_type,
        "payload": payload
    })


