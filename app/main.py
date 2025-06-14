from fastapi import FastAPI, Request, Response, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response as FastAPIResponse
import logging
from dotenv import load_dotenv
from typing import Optional, Union, Dict, Any
import os
from typing import Callable, Any, Awaitable

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# List of allowed origins
ALLOWED_ORIGINS = [
    "https://www.gigabhai.com",
    "http://localhost:3000",
    "https://gigabhai.com",
    "https://api.gigabhai.com",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "https://*.gigabhai.com"
]

# Create FastAPI app with metadata
app = FastAPI(
    title="GigaBhai API",
    description="Backend API for GigaBhai AI Assistant",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

def is_origin_allowed(origin: str) -> bool:
    """Check if the origin is allowed."""
    if not origin:
        return False
    
    # Check exact matches
    if origin in ALLOWED_ORIGINS:
        return True
    
    # Check for localhost with any port
    if any(origin.startswith(f"http://{domain}") or 
           origin.startswith(f"https://{domain}")
           for domain in ["localhost", "127.0.0.1"]):
        return True
    
    # Check for gigabhai.com subdomains
    if ".gigabhai.com" in origin:
        return True
    
    return False

# Add CORS middleware with production settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r'https?://(?:localhost:\d+|127\.0\.0\.1:\d+|(?:[\w-]+\.)*gigabhai\.com)',
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # 10 minutes
)

@app.middleware("http")
async def add_cors_headers(request: Request, call_next) -> Response:
    """Middleware to add CORS headers to all responses."""
    # Handle preflight requests
    if request.method == "OPTIONS":
        response = Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={
                "Access-Control-Allow-Origin": ", ".join(ALLOWED_ORIGINS),
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "600"
            }
        )
        return response
    
    # Process the request
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error"},
            headers={
                "Access-Control-Allow-Origin": ", ".join(ALLOWED_ORIGINS),
                "Access-Control-Allow-Credentials": "true"
            }
        )
        return response
    
    # Add CORS headers to the response
    origin = request.headers.get("origin")
    if origin and is_origin_allowed(origin):
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
