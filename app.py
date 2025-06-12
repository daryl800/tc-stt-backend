from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.leancloud_init import init_leancloud

# ✅ Init LeanCloud first
init_leancloud()

# ✅ Import routers
from routes.memory_routes import router as memory_router
from routes.transcribe_routes import router as transcribe_router

app = FastAPI()

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Route registration
app.include_router(memory_router, prefix="/memory")
app.include_router(transcribe_router, prefix="/transcribe")

# ✅ Health check
@app.get("/")
def read_root():
    return {"message": "Health check ... AI-Buddy backend is running"}
