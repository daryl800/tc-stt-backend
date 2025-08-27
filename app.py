from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from config.init import init_leancloud
from routes.ws_routes import router as ws_router
from utils.filler_utils import init_filler_messages

app = FastAPI()

# ✅ Init LeanCloud first
init_leancloud()

@app.on_event("startup")
def initialize_filler_cache():
    init_filler_messages()

# ✅ Import routers
from routes.transcribe_routes import router as transcribe_router

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Route registration
app.include_router(ws_router)

app.include_router(transcribe_router, prefix="/transcribe")

# ✅ Health check
@app.get("/")
def read_root():
    return {"message": "Health check ... AI-Buddy backend is running"}

@app.on_event("startup")
async def startup_event():
    print("🚀 Backend starting up")

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Backend shutting down")

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "detail": str(exc)},
    )

