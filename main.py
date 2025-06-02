from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64
import json
import os
import traceback  # for better error debugging
from tempfile import NamedTemporaryFile


app = FastAPI()

# Enable CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust to your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tencent Cloud credentials from environment variables
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

if not TENCENT_SECRET_ID or not TENCENT_SECRET_KEY:
    print("[ERROR] Tencent Cloud credentials are not set in environment variables.")
else:
    print("[INFO] Tencent Cloud credentials loaded.")

@app.get("/")
def read_root():
    return {"message": "Tecent ASR sync version backend is running"}


@app.post("/transcribe-cantonese")
async def transcribe_sync(audio: UploadFile = File(...)):
    try:
        print(f"[INFO] Received file: {audio.filename}")
        original_ext = audio.filename.split(".")[-1].lower()

        # Save uploaded file to disk
        with NamedTemporaryFile(delete=False, suffix=f".{original_ext}") as input_tmp:
            input_tmp.write(await audio.read())
            input_path = input_tmp.name
        print(f"[INFO] Saved input file to {input_path}")

        # Convert if WebM
        # if original_ext == "webm":
        #     with NamedTemporaryFile(delete=False, suffix=".wav") as output_tmp:
        #         output_path = output_tmp.name

        #     print(f"[INFO] Converting WebM to WAV: {input_path} → {output_path}")
        #     ffmpeg.input(input_path).output(output_path, format='wav', ar='16000', ac=1).run(overwrite_output=True)
        # else:
        #     output_path = input_path  # Use original

        # Read and encode audio
        with open(output_path, "rb") as f:
            audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        print(f"[INFO] Prepared audio, size = {len(audio_bytes)} bytes")

        # Set voice format for Tencent
        voice_format = "wav" if original_ext == "webm" else original_ext

        # Tencent ASR setup
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")

        req = models.SentenceRecognitionRequest()
        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_yue",
            "SourceType": 1,
            "VoiceFormat": voice_format,
            "UsrAudioKey": "test-key",
            "Data": audio_base64,
        }

        print("[INFO] Sending transcription request to Tencent Cloud...")
        req.from_json_string(json.dumps(params))
        resp = client.SentenceRecognition(req)

        print(f"[INFO] Transcription result: {resp.Result}")
        return {"transcription": resp.Result}

    except Exception as e:
        print("[ERROR] Transcription failed:")
        print(f"[ERROR] Exception: {str(e)}")
        traceback_str = traceback.format_exc()
        print(f"[ERROR] Traceback:\n{traceback_str}")
        return {"error": str(e)}

    finally:
        # Clean up temp files
        try:
            os.remove(input_path)
            if original_ext == "webm":
                os.remove(output_path)
            print("[INFO] Temp files deleted.")
        except Exception as cleanup_err:
            print(f"[WARNING] Failed to delete temp files: {cleanup_err}")
