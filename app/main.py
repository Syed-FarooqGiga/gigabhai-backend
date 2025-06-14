from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from dotenv import load_dotenv
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="GigaBhai API",
    description="API for GigaBhai - Your AI Assistant",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost:3000|www\.gigabhai\.com|gigabhai\.com|api\.gigabhai\.com|www\.gigabhai\.com:.*|localhost:.*)",
    allow_origins=[
        "https://www.gigabhai.com",
        "http://localhost:3000",
        "https://gigabhai.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # 10 minutes
)

# Import and include routers
from app.api.endpoints import speech as speech_endpoints
from app.api.endpoints import chat as chat_endpoints

# Include routers
app.include_router(
    speech_endpoints.router,
    prefix="/api/speech",
    tags=["speech"]
)

app.include_router(
    chat_endpoints.router,
    prefix="/api/chat",
    tags=["chat"]
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to GigaBhai API",
        "docs": "/docs",
        "redoc": "/redoc"
    }
