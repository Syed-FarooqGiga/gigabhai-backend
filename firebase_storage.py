import os
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from firebase_admin import storage, firestore
import firebase_admin
from firebase_admin import credentials
from config import FIREBASE_STORAGE_BUCKET

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    # Check if Firebase app is already initialized
    if not firebase_admin._apps:
        # Get the service account file path from environment variable
        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        
        if not service_account_path:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON environment variable not set.")
        
        # For Linux server, handle Windows-style paths if present
        if service_account_path.startswith('C:'):
            # Extract just the filename and look in the current directory
            filename = os.path.basename(service_account_path)
            service_account_path = os.path.join(os.getcwd(), filename)
            logger.info(f"Using local service account file: {service_account_path}")
        
        # Normalize the path for the current OS
        service_account_path = os.path.normpath(service_account_path)
        
        if not os.path.exists(service_account_path):
            # Try to find the file in the current directory
            filename = os.path.basename(service_account_path)
            local_path = os.path.join(os.getcwd(), filename)
            if os.path.exists(local_path):
                service_account_path = local_path
                logger.info(f"Found service account file at: {service_account_path}")
            else:
                raise FileNotFoundError(f"Firebase service account file not found at: {service_account_path}")
        
        # Initialize Firebase
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', '')
        })
        logger.info("Firebase Storage initialized successfully")

except Exception as e:
    logger.error(f"Failed to initialize Firebase Storage: {str(e)}")
    raise

# Initialize Firebase Storage and Firestore
bucket = storage.bucket()
db = firestore.client()

async def upload_meme(
    file_data: bytes, 
    file_name: str, 
    content_type: str, 
    user_id: str, 
    profile_id: str = None,
    caption: str = "", 
    category: str = "general"
) -> Dict[str, str]:
    """
    Upload a meme to Firebase Storage and store its metadata in Firestore.
    
    Args:
        file_data: The file data as bytes
        file_name: The original file name
        content_type: The MIME type of the file
        user_id: The ID of the user uploading the meme
        profile_id: The profile ID for data isolation
        caption: Optional caption for the meme
        category: Category for the meme (default: 'general')
        
    Returns:
        Dict containing the public URL and file metadata
    """
    try:
        # Generate a unique filename to prevent collisions
        file_extension = os.path.splitext(file_name)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Use profile_id for storage path if available
        storage_path = f"memes/{profile_id or user_id}/{unique_filename}"
        
        # Upload the file to Firebase Storage
        blob = bucket.blob(storage_path)
        blob.upload_from_string(
            file_data,
            content_type=content_type
        )
        
        # Make the blob publicly accessible
        blob.make_public()
        
        # Store metadata in Firestore
        meme_data = {
            'user_id': user_id,
            'profile_id': profile_id,
            'file_name': file_name,
            'storage_path': storage_path,
            'public_url': blob.public_url,
            'content_type': content_type,
            'caption': caption,
            'category': category,
            'uploaded_at': firestore.SERVER_TIMESTAMP,
            'size': len(file_data)
        }
        
        # Add to Firestore
        meme_ref = db.collection('memes').document()
        await meme_ref.set(meme_data)
        
        return {
            'id': meme_ref.id,
            'public_url': blob.public_url,
            'file_name': file_name,
            'content_type': content_type,
            'caption': caption,
            'category': category,
            'uploaded_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error uploading meme: {str(e)}")
        # Try to clean up if there was an error after blob was created
        if 'blob' in locals() and blob.exists():
            try:
                blob.delete()
            except Exception as delete_error:
                logger.error(f"Error cleaning up blob after failed upload: {str(delete_error)}")
        raise

async def get_memes(
    user_id: str, 
    profile_id: str = None, 
    category: str = None,
    limit: int = 50
) -> List[Dict[str, any]]:
    """
    Retrieve memes for a user from Firestore.
    
    Args:
        user_id: The ID of the user
        profile_id: The profile ID for data isolation
        category: Optional category filter
        limit: Maximum number of memes to return
        
    Returns:
        List of meme metadata dictionaries
    """
    try:
        # Build the query
        query = db.collection('memes').where('user_id', '==', user_id)
        
        # Add profile filter if provided
        if profile_id:
            query = query.where('profile_id', '==', profile_id)
            
        # Add category filter if provided
        if category:
            query = query.where('category', '==', category)
            
        # Order by upload time (newest first) and limit results
        query = query.order_by('uploaded_at', direction='DESCENDING').limit(limit)
        
        # Execute the query
        results = await query.get()
        
        # Process results
        memes = []
        for doc in results:
            meme_data = doc.to_dict()
            meme_data['id'] = doc.id
            # Convert Firestore timestamp to ISO format
            if 'uploaded_at' in meme_data:
                meme_data['uploaded_at'] = meme_data['uploaded_at'].isoformat()
            memes.append(meme_data)
            
        return memes
        
    except Exception as e:
        logger.error(f"Error retrieving memes: {str(e)}")
        raise

async def delete_meme(
    meme_id: str, 
    user_id: str, 
    profile_id: str = None
) -> bool:
    """
    Delete a meme from both Storage and Firestore.
    
    Args:
        meme_id: The ID of the meme to delete
        user_id: The ID of the user making the request
        profile_id: The profile ID for data isolation
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Get the meme document
        meme_ref = db.collection('memes').document(meme_id)
        meme_doc = await meme_ref.get()
        
        if not meme_doc.exists:
            logger.warning(f"Meme {meme_id} not found")
            return False
            
        meme_data = meme_doc.to_dict()
        
        # Check permissions
        if meme_data['user_id'] != user_id:
            logger.warning(f"User {user_id} is not authorized to delete meme {meme_id}")
            return False
            
        if profile_id and meme_data.get('profile_id') != profile_id:
            logger.warning(f"Profile {profile_id} is not authorized to delete meme {meme_id}")
            return False
            
        # Delete from Storage
        if 'storage_path' in meme_data:
            blob = bucket.blob(meme_data['storage_path'])
            if blob.exists():
                blob.delete()
                logger.info(f"Deleted blob {meme_data['storage_path']}")
        
        # Delete from Firestore
        await meme_ref.delete()
        logger.info(f"Deleted meme document {meme_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting meme {meme_id}: {str(e)}")
        return False
