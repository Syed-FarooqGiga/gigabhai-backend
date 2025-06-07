import firebase_admin
from firebase_admin import credentials, auth
from config import (
    FIREBASE_API_KEY,
    FIREBASE_AUTH_DOMAIN,
    FIREBASE_PROJECT_ID,
    FIREBASE_STORAGE_BUCKET,
    FIREBASE_MESSAGING_SENDER_ID,
    FIREBASE_APP_ID
)
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK using service account JSON file (recommended)
SERVICE_ACCOUNT_PATH = r"C:/Users/syedf/Downloads/giga-bhai18-firebase-adminsdk-fbsvc-bd1f29961d.json"
try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    logger.info(f"Firebase credentials loaded from service account file: {SERVICE_ACCOUNT_PATH}")
except Exception as e:
    logger.error(f"Error loading Firebase credentials from file: {SERVICE_ACCOUNT_PATH} - {str(e)}")
    raise

from config import FIREBASE_STORAGE_BUCKET

try:
    firebase_admin.initialize_app(cred, {
        "storageBucket": FIREBASE_STORAGE_BUCKET
    })
    logger.info(f"Firebase Admin SDK initialized successfully with service account file. Storage bucket: {FIREBASE_STORAGE_BUCKET}")
except Exception as e:
    logger.error(f"Error initializing Firebase Admin SDK: {str(e)}")
    raise

async def verify_firebase_token(token: str) -> dict:
    try:
        logger.debug(f"Attempting to verify token: {token[:20]}...")
        decoded_token = auth.verify_id_token(token)
        logger.debug("Token verified successfully")
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise ValueError(f"Invalid token: {str(e)}")
