from fastapi import APIRouter
from models.memory import Memory
from datetime import datetime

router = APIRouter()

@router.post("/")
def save_memory(data: dict):
    memory = Memory()
    memory.set("createdAt", datetime.now().isoformat())
    memory.set("text", data.get("text", ""))
    memory.set("mainEvent", data.get("event", ""))
    memory.set("reminderDatetime", data.get("reminderDatetime", ""))
    memory.set("location", ", ".join(data.get("location", [])))
    memory.set("isReminder", data.get("isReminder", False))
    memory.set("category", "Reminder")
    memory.set("tags", list(set(data.get("location", []))))
    memory.save()

    return {"status": "ok"}
