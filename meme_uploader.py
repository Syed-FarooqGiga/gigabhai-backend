import os
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from firebase_admin import storage, firestore
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Firebase Storage
bucket = storage.bucket()

# Initialize Firestore
db = firestore.client()

async def upload_meme(file_path: str, caption: str, category: Optional[str], profile_id: str) -> str:
    """Upload a meme to Firebase Storage and return the download URL."""
    try:
        timestamp = datetime.utcnow().isoformat().replace(':', '-')
        filename = f"{timestamp}_{os.path.basename(file_path)}"
        storage_path = f"memes/{profile_id}/{filename}"
        
        # Read file content
        with open(file_path, "rb") as file:
            file_content = file.read()
        
        # Upload to Firebase Storage
        blob = bucket.blob(storage_path)
        blob.upload_from_file(open(file_path, 'rb'), content_type=get_content_type(file_path))
        
        # Make the blob publicly accessible
        blob.make_public()
        
        # Get the public URL
        public_url = blob.public_url
        
        # Store metadata in Firestore
        meme_id = str(uuid.uuid4())
        meme_ref = db.collection('memes').document(meme_id)
        
        await meme_ref.set({
            'profile_id': profile_id,
            'url': public_url,
            'caption': caption,
            'category': category or "general",
            'created_at': firestore.SERVER_TIMESTAMP,
            'storage_path': storage_path
        })
        
        # Also add to user's memes collection for easy retrieval
        user_meme_ref = db.collection('users').document(profile_id).collection('memes').document(meme_id)
        await user_meme_ref.set({
            'meme_id': meme_id,
            'url': public_url,
            'caption': caption,
            'category': category or "general",
            'created_at': firestore.SERVER_TIMESTAMP
        })
        
        return public_url
            
    except Exception as e:
        logger.error(f"Error uploading meme: {str(e)}")
        raise e

def get_content_type(file_path: str) -> str:
    """Determine content type based on file extension"""
    extension = os.path.splitext(file_path)[1].lower()
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.webm': 'video/webm'
    }
    return content_types.get(extension, 'application/octet-stream')

async def get_memes(profile_id: Optional[str] = None) -> List[Dict]:
    """Get all memes from Firestore.
    If profile_id is provided, only get memes for that profile.
    """
    try:
        # Query Firestore for memes
        if profile_id:
            # Get memes for specific profile
            memes_ref = db.collection('memes').where('profile_id', '==', profile_id)
        else:
            # Get all memes
            memes_ref = db.collection('memes')
        
        # Order by creation time
        memes_ref = memes_ref.order_by('created_at', direction=firestore.Query.DESCENDING)
        
        # Execute query
        memes_docs = await memes_ref.get()
        
        # Format the response
        formatted_memes = []
        for doc in memes_docs:
            meme_data = doc.to_dict()
            formatted_memes.append({
                "url": meme_data.get("url"),
                "uploadTime": meme_data.get("created_at").isoformat() if meme_data.get("created_at") else "",
                "uploaderId": meme_data.get("profile_id", ""),
                "category": meme_data.get("category", "general"),
                "caption": meme_data.get("caption", "")
            })
        
        return formatted_memes
    except Exception as e:
        logger.error(f"Error getting memes: {str(e)}")
        return []
