from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from classify import classify_text
from transcribe import transcribe_sync

app = FastAPI()

# ✅ CORS config (for local frontend like Vite or React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextInput(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "Health check ... AI-Buddy backend is running"}

@app.post("/classify")
async def classify(data: TextInput):
    try:
        category = classify_text(data.text)
        return {"category": category}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe-cantonese")
async def transcribe_cantonese(audio: UploadFile = File(...)):
    try:
        transcription = await transcribe_sync(audio)  
        return transcription
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
