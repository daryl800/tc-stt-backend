from fastapi import APIRouter, File, UploadFile, HTTPException
from transcribe import transcribe_sync
from fastapi.concurrency import run_in_threadpool
import traceback
import logging

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"audio/webm", "audio/wav", "audio/mpeg"}

@router.post("/")
async def transcribe(audio: UploadFile = File(...)):
    logger.info(f"Received file: {audio.filename} | Content-Type: {audio.content_type}")

    if audio.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {audio.content_type}. Supported types: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    try:
        audio_bytes = await audio.read()
        result = await transcribe_sync(audio.filename, audio_bytes)
        return {
            "success": True,
            "filename": audio.filename,
            "transcription": result,
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error during transcription: {str(e)}\n{tb}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Transcription failed.")
