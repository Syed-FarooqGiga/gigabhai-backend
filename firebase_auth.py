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

import json

# Initialize Firebase Admin SDK from service account file
firebase_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
if not firebase_path or not os.path.exists(firebase_path):
    error_msg = "FIREBASE_SERVICE_ACCOUNT_JSON environment variable not set or file missing."
    logger.error(error_msg)
    raise ValueError(error_msg)

try:
    with open(firebase_path, 'r') as f:
        service_account_info = json.load(f)
    cred = credentials.Certificate(service_account_info)
    logger.info(f"Firebase credentials loaded successfully from {firebase_path}")
except json.JSONDecodeError as e:
    logger.error(f"Error decoding FIREBASE_SERVICE_ACCOUNT_JSON: {str(e)}")
    raise
except Exception as e:
    logger.error(f"Error initializing Firebase credentials from environment variable: {str(e)}")
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

