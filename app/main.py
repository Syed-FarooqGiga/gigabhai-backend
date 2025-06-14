from fastapi import FastAPI, Request, Response
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

# Configure CORS
origins = [
    "https://www.gigabhai.com",
    "http://localhost:3000",
    "https://gigabhai.com",
    "https://api.gigabhai.com",
    "http://localhost:8081"  # For local development
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # 10 minutes
)

# Add CORS headers to all responses
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response()
        origin = request.headers.get('origin')
        if origin in origins or any(origin.endswith(domain) for domain in ['.gigabhai.com', 'localhost']):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "600"
        return response
    
    response = await call_next(request)
    origin = request.headers.get('origin')
    if origin in origins or any(origin.endswith(domain) for domain in ['.gigabhai.com', 'localhost']):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = "*"
    return response

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
