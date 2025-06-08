from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Request, Body, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from firebase_admin import auth, firestore
from firebase_admin.exceptions import FirebaseError
from firebase_auth import verify_firebase_token
from mistral_handler import get_mistral_response
from personalities import get_personality_context
from firebase_memory_manager import (
    store_message, 
    get_chat_history, 
    get_chat_messages,
    update_chat_title,
    delete_chat
)
# from meme_uploader import upload_meme, get_memes
# from stt_handler import stt, stt_from_mic
# from tts_handler import speak
from config import UPLOAD_DIR, FIREBASE_PROJECT_ID
from dotenv import load_dotenv
import os
import json
import time
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any, Union
import httpx
from functools import lru_cache
import subprocess
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="GigaBhai API")

# Add CORS middleware
# --- CORS CONFIGURATION ---
# IMPORTANT: For production, only allow trusted domains. Credentials (cookies/auth) require explicit origins.
# If you use cookies for auth, ensure your frontend uses https://www.gigabhai.com for all requests.
# For local development, add localhost origins as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gigabhai-frontend.vercel.app",
        "https://gigabhai.com",
        "https://www.gigabhai.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- END CORS CONFIGURATION ---

# --- COOKIE SETTING UTILITY ---
from fastapi import Response

def set_cross_site_cookie(response: Response, key: str, value: str, **kwargs):
    """
    Set a cookie with SameSite=None; Secure for cross-site usage (required for auth between Vercel and Render).
    """
    response.set_cookie(
        key=key,
        value=value,
        httponly=kwargs.get('httponly', True),
        secure=True,  # Required for cross-site
        samesite="none",  # Required for cross-site
        path=kwargs.get('path', "/"),
        expires=kwargs.get('expires'),
        max_age=kwargs.get('max_age'),
        domain=kwargs.get('domain'),
    )
# --- END COOKIE UTILITY ---

# --- REDIRECT SUGGESTION (VERCEL) ---
# To unify your domain and avoid subtle cookie/CORS issues, add this to vercel.json:
# {
#   "redirects": [
#     { "source": "https://gigabhai.com/:path*", "destination": "https://www.gigabhai.com/:path*", "permanent": true }
#   ]
# }
# --- END REDIRECT SUGGESTION ---

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    personality: str
    conversation_id: Optional[str] = None
    is_new_conversation: bool = False

class ChatResponse(BaseModel):
    message: str
    timestamp: str
    personality: str
    conversation_id: Optional[str] = None  # Added conversation_id

class TokenData(BaseModel):
    token: str

class MemeUploadRequest(BaseModel):
    caption: str
    category: Optional[str] = None

class HeadingRequest(BaseModel):
    messages: List[str]

# Dependency to verify Firebase ID token and get user data
async def get_current_user(request: Request) -> Dict[str, Any]:
    """Verify Firebase ID token and return user data.
    
    Args:
        request: The incoming request
        
    Returns:
        Dict containing user data including uid and profile_id if available
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract the token from the header (format: "Bearer <token>")
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    id_token = parts[1]
    
    try:
        # Verify the ID token using Firebase Admin SDK
        decoded_token = await verify_firebase_token(id_token)
        if not decoded_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get the user record to access custom claims and other user data
        try:
            user = auth.get_user(decoded_token['uid'])
            user_data = {
                'uid': user.uid,
                'email': user.email,
                'email_verified': user.email_verified,
                'display_name': user.display_name,
                'phone_number': user.phone_number,
                'photo_url': user.photo_url,
                'disabled': user.disabled,
                'custom_claims': user.custom_claims or {}
            }
            
            # Add profile_id from custom claims if available
            if user.custom_claims and 'profile_id' in user.custom_claims:
                user_data['profile_id'] = user.custom_claims['profile_id']
            else:
                # Generate profile_id based on UID and provider ID for data isolation
                provider_id = None
                if user.provider_data and len(user.provider_data) > 0:
                    provider_id = user.provider_data[0].provider_id
                else:
                    # Default to 'firebase' if no provider data available
                    provider_id = 'firebase'
                
                # Create profile_id in format: uid_providerId
                profile_id = f"{user.uid}_{provider_id}"
                user_data['profile_id'] = profile_id
                
                # Try to save this profile_id to custom claims for future use
                try:
                    try:
                        claims = user.custom_claims if user.custom_claims else {}
                        claims['profile_id'] = profile_id
                        auth.set_custom_user_claims(user.uid, claims)
                        logging.info(f"Set profile_id in custom claims for user {user.uid}")
                    except Exception as e:
                        # Don't fail if we can't set custom claims, just log the error
                        logging.error(f"Failed to set custom claims: {str(e)}")
                except Exception as e:
                    # Don't fail if we can't set custom claims, just log the error
                    logging.error(f"Failed to set custom claims: {str(e)}")
            
            logging.info(f"User authenticated successfully: {user.uid} with profile_id: {user_data.get('profile_id')}")
            return user_data
        except ValueError as e:
            logging.error(f"Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token: {str(e)}"
            )
    except ValueError as e:
        # Specific error for token validation failures
        logging.error(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        # General error handling
        logging.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )

# Cache for frequently asked questions
@lru_cache(maxsize=100000)
def get_cached_response(message: str, personality: str) -> Optional[str]:
    return None

# API endpoints

# @app.post("/upload-meme")
# async def upload_meme_endpoint(
#     file: UploadFile = File(...),
#     caption: str = Body(...),
#     category: Optional[str] = Body(None),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Upload a meme file to Firebase Storage and store its metadata in Firestore.
#     
#     The file is stored in a user-specific directory in the Firebase Storage bucket,
#     and metadata is stored in the 'memes' collection in Firestore.
#     """
#     try:
#         # Read file content
#         contents = await file.read()
#         
#         # Validate file size (e.g., 5MB max)
#         if len(contents) > 5 * 1024 * 1024:  # 5MB
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="File size exceeds maximum allowed size of 5MB"
#             )
#         
#         # Upload to Firebase Storage
#         result = await upload_meme(
#             file_data=contents,
#             file_name=file.filename,
#             content_type=file.content_type or "application/octet-stream",
#             user_id=current_user.get("uid"),
#             profile_id=current_user.get("profile_id"),
#             caption=caption,
#             category=category or "general"
#         )
#         
#         return {
#             "success": True,
#             "message": "File uploaded successfully",
#             "data": result
#         }
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error uploading meme: {str(e)}")
#         logger.error(traceback.format_exc())
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to upload file: {str(e)}"
#         )

# @app.get("/memes")
# async def get_memes_endpoint(
#     category: Optional[str] = None,
#     limit: int = 50,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Retrieve memes for the authenticated user from Firestore.
#     
#     Args:
#         category: Optional category filter
#         limit: Maximum number of memes to return (default: 50, max: 100)
#         current_user: The authenticated user from the dependency
#         
#     Returns:
#         List of meme metadata objects with public URLs
#     """
#     try:
#         # Validate limit
#         limit = max(1, min(limit, 100))  # Enforce reasonable limits
#         
#         # Get memes from Firebase
#         memes = await get_memes(
#             user_id=current_user.get("uid"),
#             profile_id=current_user.get("profile_id"),
#             category=category,
#             limit=limit
#         )
#         
#         return {
#             "success": True,
#             "count": len(memes),
#             "data": memes
#         }
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error retrieving memes: {str(e)}")
#         logger.error(traceback.format_exc())
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to retrieve memes"
#         )

# @app.delete("/memes/{meme_id}")
# async def delete_meme_endpoint(
#     meme_id: str,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Delete a meme from both Firebase Storage and Firestore.
#     
#     Only the owner of the meme can delete it.
#     """
#     try:
#         success = await delete_meme(
#             meme_id=meme_id,
#             user_id=current_user.get("uid"),
#             profile_id=current_user.get("profile_id")
#         )
#         
#         if not success:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Meme not found or you don't have permission to delete it"
#             )
#             
#         return {
#             "success": True,
#             "message": "Meme deleted successfully"
#         }
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting meme {meme_id}: {str(e)}")
#         logger.error(traceback.format_exc())
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to delete meme"
#         )

@app.get("/auth/test")
async def test_auth_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Test endpoint to verify authentication is working correctly.
    This endpoint simply returns the user data if the token is valid.
    """
    return {
        "success": True,
        "message": "Authentication successful",
        "user": {
            "uid": current_user.get("uid"),
            "email": current_user.get("email"),
            "profile_id": current_user.get("profile_id"),
            "provider": current_user.get("provider_id"),
        }
    }

@app.post("/get-test-token")
async def get_test_token():
    try:
        # Try to get existing user or create new one
        try:
            user = auth.get_user_by_email("test@example.com")
        except auth.UserNotFoundError:
            user = auth.create_user(
                email="test@example.com",
                password="test123456"
            )
        
        # Get an ID token
        id_token = auth.create_custom_token(user.uid)
        
        # Exchange custom token for ID token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}",
                json={"token": id_token.decode(), "returnSecureToken": True}
            )
            response_data = response.json()
            if "error" in response_data:
                raise HTTPException(status_code=500, detail=response_data["error"]["message"])
            return {"token": response_data["idToken"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send-otp")
async def send_otp(data: dict = Body(...)):
    phone = data.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")
    # TODO: Integrate with real OTP service (e.g., Twilio, Firebase)
    # For now, just simulate success
    return {"success": True, "message": f"OTP sent to {phone}"}

@app.post("/verify-otp")
async def verify_otp(data: dict = Body(...)):
    phone = data.get("phone")
    otp = data.get("otp")
    if not phone or not otp:
        raise HTTPException(status_code=400, detail="Phone and OTP required")
    # TODO: Integrate with real OTP verification
    # For now, just simulate success and return a fake token
    return {"success": True, "token": "FAKE_TOKEN_FOR_DEMO"}

@app.post("/login-email")
async def login_email(data: dict = Body(...)):
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    # Use Firebase REST API to sign in
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}",
            json={"email": email, "password": password, "returnSecureToken": True}
        )
        response_data = response.json()
        if "error" in response_data:
            raise HTTPException(status_code=401, detail=response_data["error"]["message"])
        return {
            "success": True,
            "user": {"uid": response_data["localId"], "email": email},
            "token": response_data["idToken"]
        }

@app.post("/login-google")
async def login_google(data: dict = Body(...)):
    id_token = data.get("idToken")
    if not id_token:
        raise HTTPException(status_code=400, detail="Google ID token required")
    # Verify Google ID token with Firebase
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        # Create a custom token for this user
        custom_token = auth.create_custom_token(uid)
        return {"token": custom_token.decode() if hasattr(custom_token, 'decode') else custom_token}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/personalities")
async def get_personalities():
    try:
        return {
            "personalities": [
                {
                    "id": "swag",
                    "name": "Swag Bhai",
                    "avatar": "🕶️",
                    "description": "Yo bro! Let's keep it real and swaggy!",
                    "theme": {
                        "primary": "#FF6B6B",
                        "secondary": "#4ECDC4",
                        "background": "#2D3436",
                        "text": "#FFFFFF"
                    }
                },
                {
                    "id": "ceo",
                    "name": "CEO Bhai",
                    "avatar": "👔",
                    "description": "Let's discuss business and success strategies.",
                    "theme": {
                        "primary": "#2D3436",
                        "secondary": "#0984E3",
                        "background": "#FFFFFF",
                        "text": "#2D3436"
                    }
                },
                {
                    "id": "roast",
                    "name": "Roast Bhai",
                    "avatar": "🔥",
                    "description": "Ready for some spicy roasts?",
                    "theme": {
                        "primary": "#E17055",
                        "secondary": "#FF7675",
                        "background": "#2D3436",
                        "text": "#FFFFFF"
                    }
                },
                {
                    "id": "vidhyarthi",
                    "name": "Vidhyarthi Bhai",
                    "avatar": "📚",
                    "description": "Let's learn and grow together!",
                    "theme": {
                        "primary": "#6C5CE7",
                        "secondary": "#A8E6CF",
                        "background": "#FFFFFF",
                        "text": "#2D3436"
                    }
                },
                {
                    "id": "jugadu",
                    "name": "Jugadu Bhai",
                    "avatar": "🔧",
                    "description": "Need a jugaad? I'm your guy!",
                    "theme": {
                        "primary": "#FDCB6E",
                        "secondary": "#00B894",
                        "background": "#FFFFFF",
                        "text": "#2D3436"
                    }
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mistral-heading")
async def generate_heading(request: HeadingRequest):
    try:
        # Create a system prompt for title generation that focuses on content
        system_prompt = """You are a helpful assistant that generates extremely concise titles for conversations. 
        Focus ONLY on the main topic or theme discussed in the messages, ignoring any personality or style of communication.
        The title should be just 1-2 words that capture the essence of what was actually discussed.
        Use impactful, memorable words that reflect the content.
        Respond with ONLY the title, no additional text or explanation.
        Do not include personality names or styles in the title."""
        
        # Combine messages into a single context, focusing on the actual content
        conversation_context = "\n".join([
            msg for msg in request.messages 
            if not msg.startswith("[SPEECH]")  # Exclude speech indicators
        ])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a 1-2 word title that captures the main topic discussed in this conversation:\n{conversation_context}"}
        ]
        
        heading = await get_mistral_response(messages)
        
        # Clean up the response to ensure it's just the title
        heading = heading.strip()
        if heading.startswith('"') and heading.endswith('"'):
            heading = heading[1:-1]
        
        # Ensure the heading is not too long (max 2 words)
        words = heading.split()
        if len(words) > 2:
            heading = " ".join(words[:2])
        
        return {"heading": heading}
    except Exception as e:
        print("Exception in /mistral-heading:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Add new endpoint for conversation management
@app.post("/chat")
async def chat(request: Request, current_user: dict = Depends(get_current_user)):
    """Handle chat messages and generate responses using Mistral.
    
    This endpoint processes incoming chat messages, retrieves conversation history,
    generates a response using Mistral, and stores the conversation in Firestore.
    """
    try:
        data = await request.json()
        message = data.get("message")
        personality = data.get("personality", "swag")
        conversation_id = data.get("conversation_id")
        
        if not message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                             detail="Message is required")

        # Specific response for Mythili L
        # Ensure 'message' is not None before calling strip() and lower()
        if message and message.strip().lower() == "i am mythili from tumkur":
            logger.info(f"Special message 'I am Mythili from Tumkur' received from user {current_user.get('uid')}")
            special_response_text = "ohh woww u r the friend of Syed Farooq and a heart broken ex of Harshith R how is life now"
            
            # This special response currently bypasses normal message storage in Firestore.
            # If you want this interaction to be saved, you would add calls to store_message here
            # for both the user's message and this AI response, ensuring conversation_id is handled.

            return ChatResponse(
                message=special_response_text,
                timestamp=datetime.now().isoformat(),
                personality=personality, # Use the personality from the original request
                conversation_id=conversation_id # Pass the conversation_id from the request
            )
        
        # Get user ID and profile ID
        user_id = current_user.get('uid')
        profile_id = current_user.get('profile_id')
        
        # Get personality context
        personality_context = get_personality_context(personality)
        
        # Get chat history for context if conversation_id is provided
        chat_history = []
        if conversation_id:
            try:
                chat_history = await get_chat_messages(
                    chat_id=conversation_id,
                    user_id=user_id,
                    profile_id=profile_id,
                    limit=10  # Get last 10 messages for context
                )
                # Reverse to maintain chronological order
                chat_history.reverse()
            except Exception as e:
                logger.warning(f"Error fetching chat history: {str(e)}")
                # Continue with empty history if there's an error
        
        # Detect queries about the AI's creator and override response if matched
        creator_patterns = [
            "who created you", "who is your creator", "who built you", "who made you", "who developed you", "your creator", "your developer", "your owner", "your father", "who is your father", "who is your owner", "who is your developer", "about your creator", "about your developer", "about your owner", "about your father", "about this ai", "who designed you", "who programmed you", "who coded you", "who is behind you", "who is your maker", "who invented you", "who is the maker", "who is the inventor", "who is the founder", "who is the person behind you", "who is the person who created you", "who is the person who built you", "who is the person who made you", "who is the person who developed you", "who is the person who owns you", "who is the person who designed you", "who is the person who programmed you", "who is the person who coded you", "who is the person behind this ai", "who is the person behind this assistant", "who is the person behind this bot", "who is the person behind this chatbot", "who is the person behind this application", "who is the person behind this app", "who is the person behind this project", "who is the person behind this software", "who is the person behind this platform", "who is the person behind this system", "who is the person behind this service", "who is the person behind this tool", "who is the person behind this technology", "who is the person behind this solution", "who is the person behind this product", "who is the person behind this innovation", "who is the person behind this creation", "who is the person behind this invention", "who is the person behind this startup", "who is the person behind this company", "who is the person behind this team", "who is the person behind this organization", "who is the person behind this group", "who is the person behind this entity", "who is the person behind this business", "who is the person behind this firm", "who is the person behind this agency", "who is the person behind this enterprise", "who is the person behind this venture", "who is the person behind this initiative", "who is the person behind this endeavor", "who is the person behind this effort", "who is the person behind this work", "who is the person behind this achievement", "who is the person behind this accomplishment", "who is the person behind this success", "who is the person behind this breakthrough", "who is the person behind this discovery", "who is the person behind this advancement", "who is the person behind this progress", "who is the person behind this improvement", "who is the person behind this upgrade", "who is the person behind this enhancement", "who is the person behind this development", "who is the person behind this evolution", "who is the person behind this revolution", "who is the person behind this transformation", "who is the person behind this change", "who is the person behind this shift", "who is the person behind this transition", "who is the person behind this move", "who is the person behind this step", "who is the person behind this leap", "who is the person behind this jump", "who is the person behind this rise", "who is the person behind this growth", "who is the person behind this expansion", "who is the person behind this extension", "who is the person behind this spread", "who is the person behind this outreach", "who is the person behind this reach", "who is the person behind this impact", "who is the person behind this influence", "who is the person behind this contribution", "who is the person behind this input", "who is the person behind this support", "who is the person behind this help", "who is the person behind this aid", "who is the person behind this assistance", "who is the person behind this backing", "who is the person behind this sponsorship", "who is the person behind this patronage", "who is the person behind this funding", "who is the person behind this investment", "who is the person behind this finance", "who is the person behind this money", "who is the person behind this capital", "who is the person behind this resource", "who is the person behind this asset", "who is the person behind this property", "who is the person behind this wealth", "who is the person behind this fortune", "who is the person behind this riches", "who is the person behind this treasure", "who is the person behind this gold", "who is the person behind this silver", "who is the person behind this diamond", "who is the person behind this jewel", "who is the person behind this gem", "who is the person behind this pearl", "who is the person behind this stone", "who is the person behind this rock", "who is the person behind this mineral", "who is the person behind this metal", "who is the person behind this element", "who is the person behind this material", "who is the person behind this substance", "who is the person behind this thing", "who is the person behind this object", "who is the person behind this item", "who is the person behind this piece", "who is the person behind this part", "who is the person behind this component", "who is the person behind this element", "who is the person behind this feature", "who is the person behind this aspect", "who is the person behind this facet", "who is the person behind this side", "who is the person behind this angle", "who is the person behind this perspective", "who is the person behind this view", "who is the person behind this outlook", "who is the person behind this approach", "who is the person behind this method", "who is the person behind this technique", "who is the person behind this process", "who is the person behind this procedure", "who is the person behind this practice", "who is the person behind this operation", "who is the person behind this activity", "who is the person behind this action", "who is the person behind this act", "who is the person behind this deed", "who is the person behind this performance", "who is the person behind this execution", "who is the person behind this implementation", "who is the person behind this realization", "who is the person behind this fulfillment", "who is the person behind this completion"]
        import re
        message_lower = message.lower() if message else ""
        # Patterns that should trigger the Syed Farooq custom response
        syed_farooq_patterns = [
            r"^who\s+is\s+syed\s+farooq[\s\?\.!]*$",
            r"^tell\s+me\s+about\s+syed\s+farooq[\s\?\.!]*$",
            r"^describe\s+syed\s+farooq[\s\?\.!]*$",
            r"^about\s+syed\s+farooq[\s\?\.!]*$",
            r"^syed\s+farooq[\s\?\.!]*$",
            r"^what\s+is\s+syed\s+farooq[\s\?\.!]*$",
            r"^syed\s+farooq\s+bio[\s\?\.!]*$",
            r"^syed\s+farooq\s+biography[\s\?\.!]*$",
            r"^syed\s+farooq\s+summary[\s\?\.!]*$",
            r"^syed\s+farooq\s+profile[\s\?\.!]*$",
            r"^syed\s+farooq\s+ai\s+engineer[\s\?\.!]*$",
            r"^syed\s+farooq\s+from\s+india[\s\?\.!]*$"
        ]
        matched_syed = any(re.match(pattern, message_lower.strip()) for pattern in syed_farooq_patterns)
        if matched_syed:
            response = "Syed Farooq is a great guy who created me and is an excellent AI engineer from India."
        else:
            matched_creator = any(pattern in message_lower for pattern in creator_patterns)
            if matched_creator:
                response = "Syed Farooq the AI engineering student from India created me in June 2025."
            else:
                try:
                    # Format messages for Mistral API
                    messages = []
                    # Add personality context (system messages)
                    for msg in personality_context:
                        if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            messages.append({
                                "role": msg['role'],
                                "content": str(msg['content']) if not isinstance(msg['content'], str) else msg['content']
                            })
                    # Add chat history if available
                    for msg in chat_history:
                        if msg.get('role') and msg.get('content'):
                            messages.append({
                                "role": msg['role'],
                                "content": msg['content']
                            })
                    # Add the current user message
                    messages.append({
                        "role": "user",
                        "content": message
                    })
                    # Log the full prompt/messages sent to the LLM for debugging
                    logger.info(f"Prompt sent to LLM (Mistral): {json.dumps(messages, ensure_ascii=False, indent=2)}")
                    response = await get_mistral_response(messages)
                except Exception as e:
                    logger.error(f"Error generating response with Mistral: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to generate response"
                    )
        
        # Store the conversation in Firestore
        try:
            conversation_id = await store_message(
                user_id=user_id,
                profile_id=profile_id,
                personality=personality,
                message=message,
                response=response,
                chat_id=conversation_id
            )
        except Exception as e:
            logger.error(f"Error storing message in Firestore: {str(e)}")
            if '404' in str(e):
                logger.error(f"Firestore 404: Conversation document missing for chat_id={conversation_id}, user_id={user_id}, profile_id={profile_id}. This usually means the conversation was never created or was deleted.")
            # Don't fail the request if storage fails, just log it
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
        
        # Sanitize the response to remove any mention of 'Mistral' or 'Mistral AI'
        if isinstance(response, str):
            forbidden_keywords = ["mistral ai", "mistral", "Mistral AI", "Mistral"]
            for keyword in forbidden_keywords:
                response = response.replace(keyword, "AI")

        # Return the sanitized response
        return {
            "message": response,
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "personality": personality
        }
        
    except HTTPException as he:
        logger.error(f"HTTP error in chat endpoint: {str(he.detail)}")
        raise
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body"
        )
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@app.put("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Update a conversation's metadata (title, personality, etc.) in Firestore."""
    try:
        data = await request.json()
        title = data.get("title")
        personality = data.get("personality")
        
        if not any([title, personality]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (title or personality) is required"
            )
        
        # Get user ID and profile ID from the authenticated user
        user_id = current_user.get("uid")
        profile_id = current_user.get("profile_id")
        
        # Prepare update data
        update_data = {
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        if title is not None:
            update_data['title'] = title
        if personality is not None:
            update_data['personality'] = personality
        
        # Update the conversation in Firestore
        db = firestore.client()
        conversation_ref = db.collection('users').document(profile_id or user_id)\
                             .collection('conversations').document(conversation_id)
        
        # Check if the conversation exists and belongs to the user
        conversation = await conversation_ref.get()
        if not conversation.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
            
        await conversation_ref.update(update_data)
        
        # Get the updated conversation
        updated_conversation = await conversation_ref.get()
        
        return {
            "success": True,
            "conversation": {
                "id": conversation_id,
                "title": updated_conversation.get("title"),
                "personality": updated_conversation.get("personality"),
                "profile_id": profile_id,
                "user_id": user_id,
                "updated_at": updated_conversation.get("updated_at").isoformat() if updated_conversation.get("updated_at") else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation"
        )

@app.get("/conversations")
async def get_conversations_endpoint(current_user: dict = Depends(get_current_user)):
    """Get the user's conversations from Firestore."""
    try:
        # Get user ID and profile ID from the authenticated user
        user_id = current_user.get("uid")
        profile_id = current_user.get("profile_id")
        
        # Fetch conversations from Firestore
        conversations = await get_chat_history(user_id, profile_id)
        
        return {
            "success": True,
            "conversations": conversations
        }
    except Exception as e:
        logger.error(f"Error fetching conversations: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversations"
        )

@app.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a conversation and all its messages from Firestore."""
    try:
        # Get user ID and profile ID from the authenticated user
        user_id = current_user.get("uid")
        profile_id = current_user.get("profile_id")
        
        # Delete the conversation and its messages
        success = await delete_chat(conversation_id, user_id, profile_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or could not be deleted"
            )
            
        return {
            "success": True,
            "message": "Conversation deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
