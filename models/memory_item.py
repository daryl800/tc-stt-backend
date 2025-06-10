from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MemoryItem(BaseModel):
    category: str = "General"
    transcription: str
    mainEvent: str
    reminderDatetime: str = ""
    isReminder: bool = False
    location: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    createdAt: datetime
    originalVoice_Url: Optional[str] = None
    rawLLMOutput: Optional[dict] = None
    sourceLang: Optional[str] = "yue-HK"
    userId: Optional[str] = None
