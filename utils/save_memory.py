from models.leancloud_memory import Memory
from models.memory_item import MemoryItem
from datetime import datetime
import requests
import uuid
from config.constants import LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY


def upload_audio_to_leancloud(audio_bytes: bytes, filename: str = None) -> str:
    if not filename:
        filename = f"memory_{uuid.uuid4().hex}.wav"

    headers = {
        "X-LC-Id": LEANCLOUD_APP_ID,
        "X-LC-Key": LEANCLOUD_APP_KEY,
        "Content-Type": "audio/wav"
    }

    response = requests.post(
        f"https://{LEANCLOUD_APP_ID.lower()}.api.lncldglobal.com/1.1/files/{filename}",
        headers=headers,
        data=audio_bytes
    )

    response.raise_for_status()
    return response.json()["url"]


def save_to_leancloud(memory_item: MemoryItem, audio_bytes: bytes = None) -> str:
    memory = Memory()

    # Basic fields
    for field, value in memory_item.dict().items():
        if value is not None:
            memory.set(field, value)

    # Audio
    if audio_bytes:
        voice_url = upload_audio_to_leancloud(audio_bytes)
        memory.set("originalVoice_Url", voice_url)

    memory.save()
    print(f"[INFO] Memory saved with ID: {memory.id} at {datetime.now().isoformat()}")
    return memory.id
