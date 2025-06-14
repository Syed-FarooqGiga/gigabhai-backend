from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import chat, speech, gigs, auth
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Allowed frontend origins
origins = [
    "https://www.gigabhai.com",  # Your production frontend
    "http://localhost:3000",     # For local dev testing
    "http://127.0.0.1:3000"
]

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for allowed domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Only allow your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
@app.get("/")
def root():
    return {"message": "Welcome to GigaBhai API"}

@app.get("/health")
def health():
    return {"status": "ok"}

# Include routers
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(speech.router, prefix="/api", tags=["Speech"])
app.include_router(gigs.router, prefix="/api", tags=["Gigs"])
app.include_router(auth.router, prefix="/api", tags=["Auth"])
