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

def upload_audio_to_leancloud(filepath: str) -> str:
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        file_data = f.read()

    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": app_key,
        "Content-Type": "audio/wav"
    }

    url = f"{app_endPoint}/{filename}"
    response = requests.post(url, headers=headers, data=file_data)
    response.raise_for_status()
    return response.json()["url"]  # ✅ File stored, returns its URL


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
