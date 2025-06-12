from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from models.memory_item import MemoryItem
from utils.save_memory import save_to_leancloud_async

import json

router = APIRouter()

@router.post("/")
async def save_memory_endpoint(memory_json: str = Form(...), audio: UploadFile = File(None)):
    try:
        # Parse memory info
        memory_dict = json.loads(memory_json)
        memory_item = MemoryItem(**memory_dict)

        # Read audio bytes if present
        audio_bytes = await audio.read() if audio else None

        # Save to LeanCloud
        memory_id = save_to_leancloud_async(memory_item, audio_bytes)

        return {"status": "ok", "id": memory_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
