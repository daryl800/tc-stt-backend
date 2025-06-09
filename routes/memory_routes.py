from fastapi import APIRouter
from models.memory import Memory
from datetime import datetime
from leancloud import Object
import requests
import os

class Memory(Object):
    pass

# Bind to the correct class name in LeanCloud
Memory = Object.extend('memories')

router = APIRouter()

app_id = os.getenv("LEANCLOUD_APP_ID")
app_key = os.getenv("LEANCLOUD_APP_KEY")    
app_endPoint = f"https://{app_id.lower()}.api.lncldglobal.com/1.1/files"


import uuid

def upload_audio_to_leancloud(audio_bytes: bytes, filename: str = None) -> str:
    if not filename:
        filename = f"memory_{uuid.uuid4().hex}.wav"

    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": app_key,
        "Content-Type": "audio/wav"
    }

    response = requests.post(
        app_endPoint + "/{filename}",
        headers=headers,
        data=audio_bytes  # ✅ send raw bytes
    )

    response.raise_for_status()
    return response.json()["url"]

@router.post("/")
def save_memory(data: dict):
    memory = Memory()
    
    # Upload .wav audio file and get its URL
    wav_path = data.get("raw_wav")  # passed in from API or internal code
    if wav_path:
        audio_url = upload_audio_to_leancloud(wav_path)
        memory.set("audioUrl", audio_url)  # 👈 store in DB
    
    memory.set("text", data.get("text", ""))
    memory.set("mainEvent", data.get("event", ""))
    memory.set("reminderDatetime", data.get("reminderDatetime", ""))
    memory.set("location", ", ".join(data.get("location", [])))
    memory.set("isReminder", data.get("isReminder", False))
    memory.set("category", "Reminder")
    memory.set("tags", list(set(data.get("location", []))))

    memory.save()
    print(f"[INFO] Memory saved with ID: {memory.id} at {datetime.now().isoformat()}")

    return {"status": "ok"}
