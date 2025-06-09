from fastapi import APIRouter, File, UploadFile, HTTPException
from transcribe import transcribe_sync

router = APIRouter()

@router.post("/")
async def transcribe(audio: UploadFile = File(...)):
    try:
        transcription = await transcribe_sync(audio)
        return transcription
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
