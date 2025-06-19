import uuid
import aiohttp  # Async HTTP client
import asyncio
from datetime import datetime
from models.leancloud_memory import Memory
from models.memory_item import MemoryItem
from config.constants import LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY

# Assume LeanCloud's Memory.save() is synchronous
def sync_save_memory(memory: Memory) -> str:
    memory.save()
    return memory.id

async def save_to_leancloud_async(memory_item: MemoryItem, audio_bytes: bytes = None) -> str:
    memory = Memory()

    # Set basic fields (synchronous, but fast)
    for field, value in memory_item.dict().items():
        if value is not None:
            memory.set(field, value)

    # Async audio upload with aiohttp
    if audio_bytes:
        filename = f"memory_{uuid.uuid4().hex}.wav"
        headers = {
            "X-LC-Id": LEANCLOUD_APP_ID,
            "X-LC-Key": LEANCLOUD_APP_KEY,
            "Content-Type": "audio/wav"
        }
        async with aiohttp.ClientSession() as session:
            url = f"https://{LEANCLOUD_APP_ID.lower()}.api.lncldglobal.com/1.1/files/{filename}"
            try:
                async with session.post(url, headers=headers, data=audio_bytes) as response:
                    response.raise_for_status()
                    result = await response.json()
                    voice_url = result["url"]
                    memory.set("originalVoice_Url", voice_url)
            except aiohttp.ClientError as e:
                print(f"[ERROR] Audio upload failed: {e}")
                raise

    # Offload synchronous save to a background thread
    loop = asyncio.get_event_loop()
    memory_id = await loop.run_in_executor(None, sync_save_memory, memory)

    print(f"[INFO] Memory saved with ID: {memory_id} at {datetime.now().isoformat()}")
    return memory_id