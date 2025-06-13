import firebase_admin
from firebase_admin import credentials, auth
import os
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
def initialize_firebase():
    try:
        # Check if Firebase app is already initialized
        if not firebase_admin._apps:
            # Get the service account file path from environment variable
            service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
            
            if not service_account_path:
                logger.error("FIREBASE_SERVICE_ACCOUNT_JSON environment variable not set.")
                raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON environment variable not set.")
                
            # Normalize the path for the current OS
            service_account_path = os.path.normpath(service_account_path)
            
            if not os.path.exists(service_account_path):
                logger.error(f"Firebase service account file not found at: {service_account_path}")
                logger.error(f"Current working directory: {os.getcwd()}")
                raise FileNotFoundError(f"Firebase service account file not found at: {service_account_path}")
            
            try:
                # Initialize with the service account file
                cred = credentials.Certificate(service_account_path)
                logger.info(f"Successfully loaded Firebase credentials from: {service_account_path}")
            except Exception as e:
                logger.error(f"Error loading Firebase credentials: {str(e)}")
                raise
            
            # Initialize the app with the credentials
            firebase_admin.initialize_app(cred, {
                'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
            })
            
            logger.info("Firebase Admin SDK initialized successfully.")
        else:
            logger.info("Firebase Admin SDK already initialized.")
            
    except Exception as e:
        logger.error(f"Error initializing Firebase: {str(e)}")
        raise

# Initialize Firebase when this module is imported
initialize_firebase()

async def verify_firebase_token(token: str) -> dict:
    try:
        logger.debug(f"Attempting to verify token: {token[:20]}...")
        decoded_token = auth.verify_id_token(token)
        logger.debug("Token verified successfully")
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise ValueError(f"Invalid token: {str(e)}")
