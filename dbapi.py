import os
from typing import Optional

import requests  # only if you later proxy calls; safe to keep/remove
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AnyHttpUrl
from pymongo import MongoClient
from pymongo.collection import Collection

# -------------------- Config --------------------
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://phawitboo:JO3hoCXWCSXECrGB@cluster0.fvc5db5.mongodb.net/?retryWrites=true&w=majority"
)
DB_NAME = os.getenv("MONGODB_DB", "my_database")
COLL_NAME = os.getenv("MONGODB_COLL", "ngrok_tunnels")

# -------------------- App -----------------------
app = FastAPI(title="Ngrok URL Service", version="1.0.0")

# CORS: open for dev; restrict to your Netlify domain in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g., ["https://your-site.netlify.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Models --------------------
class NgrokDoc(BaseModel):
    ngrok_url: AnyHttpUrl  # validates it's a valid http/https URL string

# -------------------- DB helpers ----------------
def get_collection() -> Collection:
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Try a cheap server check once (optional)
        _ = client.admin.command("ping")
        return client[DB_NAME][COLL_NAME]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mongo connection failed: {e}")

def fetch_ngrok_url() -> Optional[str]:
    coll = get_collection()
    doc = coll.find_one({}, projection={"_id": False, "ngrok_url": True})
    return doc.get("ngrok_url") if doc else None

def upsert_ngrok_url(url: str) -> str:
    coll = get_collection()
    coll.update_one({}, {"$set": {"ngrok_url": url}}, upsert=True)
    return url

# -------------------- Routes --------------------
@app.get("/", tags=["health"])
def health():
    return {"status": "ok"}

@app.get("/get_ngrok_url", tags=["ngrok"])
def get_ngrok_url():
    url = fetch_ngrok_url()
    if not url:
        raise HTTPException(status_code=404, detail="ngrok_url not found")
    return {"ngrok_url": url}

@app.post("/set_ngrok_url", tags=["ngrok"])
def set_ngrok_url(payload: NgrokDoc):
    saved = upsert_ngrok_url(str(payload.ngrok_url))
    return {"ngrok_url": saved, "status": "updated"}
