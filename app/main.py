from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import logging
from dotenv import load_dotenv
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create FastAPI app with metadata
app = FastAPI(
    title="GigaBhai API",
    description="Backend API for GigaBhai AI Assistant",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
# List of allowed origins
origins = [
    "https://www.gigabhai.com",
    "http://localhost:3000",
    "http://localhost:8081",
    "https://gigabhai.com",
    "https://api.gigabhai.com",
    "http://127.0.0.1:8081",
    "http://localhost:19006"  # Expo web default
]

# Add CORS middleware with explicit configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",  # Allow localhost with any port
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],
    max_age=600,  # 10 minutes
)

# Import and include routers after app is created
from app.api.endpoints import chat, speech

# Include routers with proper prefixes
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(speech.router, prefix="/api/speech", tags=["Speech"])

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
        "health": "/health"
    }

# Log startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting GigaBhai API server...")
    logger.info(f"Environment: {os.getenv('ENV', 'development')}")
    logger.info(f"Firebase Project: {os.getenv('FIREBASE_PROJECT_ID', 'not set')}")
