from fastapi import APIRouter, File, UploadFile, HTTPException
from transcribe import transcribe_sync
from fastapi.concurrency import run_in_threadpool
import traceback
import logging

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

@router.post("/")
async def transcribe(audio: UploadFile = File(...)):
    print(f"Received file: {audio.filename} | content_type: {audio.content_type}")
    try:
        transcription = await run_in_threadpool(transcribe_sync, audio)
        return transcription
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    



