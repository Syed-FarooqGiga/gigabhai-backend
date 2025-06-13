import os
import uvicorn
from dotenv import load_dotenv
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Verify required environment variables
required_vars = [
    'FIREBASE_SERVICE_ACCOUNT_JSON',
    'FIREBASE_STORAGE_BUCKET',
    'FIREBASE_API_KEY',
    'FIREBASE_AUTH_DOMAIN',
    'FIREBASE_PROJECT_ID'
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Error: The following required environment variables are not set: {', '.join(missing_vars)}")
    exit(1)

# Verify service account file exists
service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
if service_account_path and not os.path.exists(service_account_path):
    logger.error(f"Error: Service account file not found at: {service_account_path}")
    exit(1)

# Import the FastAPI app after environment variables are verified
from app.main import app

if __name__ == "__main__":
    logger.info("Starting GigaBhai API server...")
    logger.info(f"Environment: {os.getenv('ENV', 'development')}")
    logger.info(f"Firebase Project: {os.getenv('FIREBASE_PROJECT_ID')}")
    
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "development") == "development",
        log_level="info"
    )
