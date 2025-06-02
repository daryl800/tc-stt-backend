from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64

app = FastAPI()

# Optional: Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace with your real Tencent credentials
TENCENT_SECRET_ID = "TENCENT_SECRET_ID"
TENCENT_SECRET_KEY = "TENCENT_SECRET_KEY"

@app.get("/")
def read_root():
    return {"message": "TECENT SentenceRecognition Backend is running!"}

@app.post("/transcribe-cantonese")
async def transcribe_cantonese(file: UploadFile = File(...)):
    # Read file into memory
    file_bytes = await file.read()

    # Encode audio to base64
    audio_base64 = base64.b64encode(file_bytes).decode("utf-8")

    # Setup credentials and client
    cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    client = asr_client.AsrClient(cred, "ap-guangzhou")

    # Configure SentenceRecognition request
    req = models.SentenceRecognitionRequest()
    req.EngineModelType = "16k_zh-HK"  # Cantonese
    req.ChannelNum = 1
    req.ResTextFormat = 0  # 0 = plain text
    req.SourceType = 1     # 1 = base64
    req.Data = audio_base64
    req.DataLen = len(file_bytes)

    # Send request
    resp = client.SentenceRecognition(req)

    # Return response
    return {"transcript": resp.Result}
