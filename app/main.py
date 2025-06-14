from fastapi import FastAPI
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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Allow localhost origins explicitly for dev
dev_origins = [
    "http://localhost:3000",
    "http://localhost:8081"
]

# Add CORS middleware (allows all *.gigabhai.com subdomains and localhost for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https:\/\/(.*\.)?gigabhai\.com",
    allow_origins=dev_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
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
        "docs": "/api/docs",
        "redoc": "/api/redoc"
    }
