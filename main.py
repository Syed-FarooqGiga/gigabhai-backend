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
from meme_uploader import upload_meme, get_memes
from stt_handler import stt, stt_from_mic
from tts_handler import speak
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8082", "http://127.0.0.1:8082", "*"],  # Explicitly include frontend URL
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

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

@app.post("/upload-meme")
async def upload_meme_endpoint(
    file: UploadFile = File(...),
    caption: str = Body(...),
    category: Optional[str] = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a meme file to Firebase Storage and store its metadata in Firestore.
    
    The file is stored in a user-specific directory in the Firebase Storage bucket,
    and metadata is stored in the 'memes' collection in Firestore.
    """
    try:
        # Read file content
        contents = await file.read()
        
        # Validate file size (e.g., 5MB max)
        if len(contents) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds maximum allowed size of 5MB"
            )
        
        # Upload to Firebase Storage
        result = await upload_meme(
            file_data=contents,
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            user_id=current_user.get("uid"),
            profile_id=current_user.get("profile_id"),
            caption=caption,
            category=category or "general"
        )
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading meme: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )

@app.get("/memes")
async def get_memes_endpoint(
    category: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve memes for the authenticated user from Firestore.
    
    Args:
        category: Optional category filter
        limit: Maximum number of memes to return (default: 50, max: 100)
        current_user: The authenticated user from the dependency
        
    Returns:
        List of meme metadata objects with public URLs
    """
    try:
        # Validate limit
        limit = max(1, min(limit, 100))  # Enforce reasonable limits
        
        # Get memes from Firebase
        memes = await get_memes(
            user_id=current_user.get("uid"),
            profile_id=current_user.get("profile_id"),
            category=category,
            limit=limit
        )
        
        return {
            "success": True,
            "count": len(memes),
            "data": memes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving memes: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memes"
        )

@app.delete("/memes/{meme_id}")
async def delete_meme_endpoint(
    meme_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a meme from both Firebase Storage and Firestore.
    
    Only the owner of the meme can delete it.
    """
    try:
        success = await delete_meme(
            meme_id=meme_id,
            user_id=current_user.get("uid"),
            profile_id=current_user.get("profile_id")
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meme not found or you don't have permission to delete it"
            )
            
        return {
            "success": True,
            "message": "Meme deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meme {meme_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete meme"
        )

@app.post("/stt")
async def stt_endpoint(
    audio: UploadFile = File(...),
    language: str = "en-US"
):
    """Convert speech to text"""
    print("\n=== STT Endpoint Called ===")
    print(f"Received file: {audio.filename}")
    print(f"Content type: {audio.content_type}")
    
    if not audio:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    # Save the uploaded file
    file_path = os.path.join(UPLOAD_DIR, audio.filename)
    try:
        # Read file content
        content = await audio.read()
        print(f"File size: {len(content)} bytes")
        print(f"First 16 bytes: {content[:16]}")
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        print(f"File saved to: {file_path}")
        
        # Convert speech to text
        print("Starting transcription...")
        text = stt(file_path, language)
        print(f"Transcription successful: {text}")
        
        return {
            "success": True,
            "text": f"[SPEECH] {text}"
        }
    except Exception as e:
        print(f"Error in transcription: {str(e)}")
        print("Full error details:")
        traceback.print_exc()
        
        # Clean up the file if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                print(f"Error cleaning up file: {str(cleanup_error)}")
        
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

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

@app.post("/stt/mic")
async def stt_mic_endpoint(
    language: str = "en-US",
    current_user: dict = Depends(get_current_user)
):
    try:
        # Convert speech to text from microphone
        text = stt_from_mic(language)
        # Add [SPEECH] prefix to indicate this is from speech input
        return {"text": f"[SPEECH]{text}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        # Save the uploaded file
        file_location = f"temp_{audio.filename}"
        print(f"Received file: {audio.filename}, content type: {audio.content_type}")
        
        with open(file_location, "wb") as file:
            content = await audio.read()
            print(f"File size: {len(content)} bytes")
            print(f"First 16 bytes: {content[:16]}")
            file.write(content)
        
        print(f"File saved at: {file_location}")
        
        # Always convert to WAV with specific parameters
        print("Converting to WAV format...")
        wav_file = convert_to_wav(file_location)
        if not wav_file:
            raise Exception("Failed to convert audio to WAV format")
        
        # Remove original file
        if os.path.exists(file_location):
            os.remove(file_location)
        
        file_location = wav_file
        print(f"Converted to WAV: {file_location}")
        
        # Transcribe the audio
        print("Starting transcription...")
        text = stt(file_location)
        print(f"Transcription result: {text}")
        
        # Clean up
        if os.path.exists(file_location):
            os.remove(file_location)
        
        return {"text": text}
    except Exception as e:
        print(f"Error in transcribe_audio: {str(e)}")
        traceback.print_exc()
        # Clean up file if it exists
        if 'file_location' in locals() and os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(
            status_code=400,
            detail=str(e)  # Return the actual error message instead of "Something went wrong"
        )

def convert_to_wav(input_file):
    try:
        output_file = input_file.rsplit('.', 1)[0] + '.wav'
        print(f"Converting {input_file} to {output_file}")
        
        # Use ffmpeg to convert to WAV with specific parameters
        result = subprocess.run([
            'ffmpeg', '-y',  # -y to overwrite output file if it exists
            '-i', input_file,
            '-acodec', 'pcm_s16le',  # Use 16-bit PCM encoding
            '-ar', '16000',  # Set sample rate to 16kHz
            '-ac', '1',  # Convert to mono
            '-f', 'wav',  # Force WAV format
            output_file
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg conversion failed: {result.stderr}")
        
        print(f"Conversion successful: {output_file}")
        return output_file
    except Exception as e:
        print(f"Error converting to WAV: {str(e)}")
        return None

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
        
        # Generate response using Mistral
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
        
        # Return the response
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
