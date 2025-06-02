from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64
import os

app = FastAPI()

# Optional: Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace with your real Tencent credentials
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

@app.get("/")
def read_root():
    return {"message": "TECENT SentenceRecognition Backend is running!"}

@app.post("/transcribe-cantonese")
async def transcribe(file: UploadFile = File(...)):
    try:
        # Save uploaded file temporarily
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Set up credentials
        cred = Credential(os.getenv("TC_SECRET_ID"), os.getenv("TC_SECRET_KEY"))
        client = asr_client.AsrClient(cred, "ap-guangzhou")

        req = models.SentenceRecognitionRequest()
        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh",  # ✅ must include this
            "SourceType": 1,
            "VoiceFormat": "mp3",
            "UsrAudioKey": "memory-clip",
            "Data": str(base64.b64encode(open(file_location, "rb").read()), "utf-8"),
        }
        req.from_json_string(json.dumps(params))

        resp = client.SentenceRecognition(req)
        return {"text": resp.Result}

    except TencentCloudSDKException as err:
        return {"error": str(err)}