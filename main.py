import os
import json
import base64
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tencent Cloud credentials (set these in your environment)
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")
REGION = "ap-hongkong"  # Adjust as needed

if not TENCENT_SECRET_ID or not TENCENT_SECRET_KEY:
    raise RuntimeError("Tencent Cloud credentials are not set in environment variables.")

# Initialize Tencent credential and client
def get_asr_client():
    cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    client = asr_client.AsrClient(cred, REGION)
    return client

@app.post("/transcribe-tencent")
async def transcribe_tencent(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()

        client = get_asr_client()

        req = models.CreateRecTaskRequest()
        params = {
            "EngineModelType": "16k_zh",  # or "16k_ca" for Cantonese, etc.
            "ChannelNum": 1,
            "ResTextFormat": 0,
            "SourceType": 1,  # 1 = base64 data
            "Data": audio_base64,
            "DataLen": len(audio_bytes)
        }
        req.from_json_string(json.dumps(params))

        resp = client.CreateRecTask(req)
        task_id = resp.Data.TaskId
        return {"task_id": task_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transcribe-tencent-result/{task_id}")
async def get_transcription_result(task_id: str):
    try:
        client = get_asr_client()
        req = models.DescribeTaskStatusRequest()
        params = {"TaskId": task_id}
        req.from_json_string(json.dumps(params))
        resp = client.DescribeTaskStatus(req)

        # Check task status: resp.Data.Status
        # 0 = waiting, 1 = processing, 2 = success, 3 = failed
        status = resp.Data.Status

        if status == 0:
            return {"status": "waiting", "message": "Task is waiting to be processed."}
        elif status == 1:
            return {"status": "processing", "message": "Task is being processed."}
        elif status == 2:
            # Success, transcription is in resp.Data.Result
            return {
                "status": "success",
                "result": resp.Data.Result,
                "audio_duration": resp.Data.AudioDuration  # seconds
            }
        elif status == 3:
            return {"status": "failed", "message": resp.Data.ErrMsg}
        else:
            return {"status": "unknown", "detail": resp.to_json_string()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
