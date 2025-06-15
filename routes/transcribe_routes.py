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
    logger.info(f"[INFO] Received audio file: {audio.filename} | Content-Type: {audio.content_type}")

    if audio.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"[INFO] Unsupported file type: {audio.content_type}. Supported types: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    try:
        audio_bytes = await audio.read()
        result = await transcribe_sync(audio.filename, audio_bytes)
        return {
            "success": True,
            "TranscriptionResponse": result,
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[ERROR] Error during transcription: {str(e)}\n{tb}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Transcription failed.")
