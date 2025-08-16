from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MemoryItem(BaseModel):
    category: str = "General"
    categoryIcon: str
    transcription: str
    mainEvent: str
    reminderDatetime: str = ""
    isReminder: bool = False
    isQuery: bool = False
    location: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    eventCreatedAt: Optional[datetime] = None
    originalVoice_Url: Optional[str] = None
    sourceLang: Optional[str] = "yue-HK"
    userId: Optional[str] = None
    reflection: Optional[str] = None
