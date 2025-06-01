from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/transcribe-tencent")
async def transcribe_tencent(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    audio_base64 = base64.b64encode(audio_bytes).decode()

    cred = credential.Credential(
        os.getenv("TENCENT_SECRET_ID"),
        os.getenv("TENCENT_SECRET_KEY")
    )
    client = asr_client.AsrClient(cred, "ap-hongkong")

    req = models.CreateRecTaskRequest()
    params = {
        "EngineModelType": "16k_zh",  # or 16k_en, 16k_ca for Cantonese
        "ChannelNum": 1,
        "ResTextFormat": 0,
        "SourceType": 1,
        "Data": audio_base64,
        "DataLen": len(audio_bytes)
    }
    req.from_json_string(json.dumps(params))

    resp = client.CreateRecTask(req)
    return {"task_id": resp.Data.TaskId}
