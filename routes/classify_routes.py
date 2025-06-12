from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from classify import classify_text

router = APIRouter()

class TextInput(BaseModel):
    text: str

@router.post("/")
async def classify(data: TextInput):
    try:
        category = classify_text(data.text)
        return {"category": category}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
