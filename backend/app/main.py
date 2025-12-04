from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prisma import Prisma
from app.api import auth, scans, system

db = Prisma()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    
    # Cleanup zombie scans (scans stuck in "Running" state from previous session)
    try:
        zombie_scans = await db.scan.update_many(
            where={"status": "Running"},
            data={"status": "Failed"}
        )
        if zombie_scans > 0:
            print(f"Startup Cleanup: Marked {zombie_scans} zombie scans as Failed.")
    except Exception as e:
        print(f"Startup Cleanup Error: {e}")
        
    yield
    await db.disconnect()

app = FastAPI(title="Pentest Web App API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
import os

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(scans.router, prefix="/scans", tags=["scans"])
app.include_router(system.router, prefix="/system", tags=["system"])

# Ensure reports directory exists
os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

@app.get("/")
def read_root():
    return {"message": "Welcome to Pentest Web App API"}
 
 
