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
origins = [
    "https://www.gigabhai.com",
    "http://localhost:3000",
    "http://localhost:8081",
    "https://gigabhai.com",
    "https://api.gigabhai.com"
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add middleware to handle CORS preflight requests
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    # Handle preflight requests
    if request.method == "OPTIONS":
        response = Response()
        origin = request.headers.get("origin")
        if origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    
    # For regular requests
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

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
