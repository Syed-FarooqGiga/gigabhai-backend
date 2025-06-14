import logging
from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Tuple
import uuid
import os
import json
from datetime import datetime
from pathlib import Path
from groq_handler import get_groq_response

# Import personality system
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from personalities import get_personality_context, PERSONALITIES, PERSONALITY_PROMPTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHAT_HISTORY_DIR = Path("chat_history")
MAX_HISTORY_LENGTH = 10  # Maximum number of messages to keep in memory

# Ensure chat history directory exists
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

router = APIRouter(tags=["chat"])

def get_chat_history_file(conversation_id: str) -> Path:
    """Get the path to the chat history file for a conversation."""
    return CHAT_HISTORY_DIR / f"{conversation_id}.json"

async def load_chat_history(conversation_id: str) -> List[Dict[str, Any]]:
    """Load chat history for a conversation."""
    history_file = get_chat_history_file(conversation_id)
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading chat history: {e}")
            return []
    return []

async def save_chat_history(conversation_id: str, messages: List[Dict[str, Any]]) -> None:
    """Save chat history for a conversation."""
    if not messages:
        return
        
    try:
        history_file = get_chat_history_file(conversation_id)
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving chat history: {e}")

def prepare_messages(
    user_message: str,
    personality_id: str,
    chat_history: List[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, str]], str]:
    """
    Prepare messages for the LLM with personality context.
    
    Args:
        user_message: The user's message
        personality_id: ID of the personality to use
        chat_history: Previous chat history (if any)
        
    Returns:
        Tuple of (messages, conversation_id)
    """
    # Get personality context
    personality = PERSONALITIES.get(personality_id, PERSONALITIES["swag_bhai"])
    context = get_personality_context(personality_id)
    
    # Prepare system message with personality
    system_message = {
        "role": "system",
        "content": context["system_prompt"]
    }
    
    # Prepare messages list with system message first
    messages = [system_message]
    
    # Add chat history if available
    if chat_history:
        # Ensure we don't exceed max history length
        for msg in chat_history[-MAX_HISTORY_LENGTH:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message.strip()
    })
    
    return messages

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    personality: str
    conversation_id: Optional[str] = None
    user_id: str
    profile_id: str
    chat_history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    status: str = "success"
    error: Optional[str] = None

# Personality validation
def validate_personality(personality_id: str) -> bool:
    """Check if a personality ID is valid."""
    return personality_id in PERSONALITIES

@router.options("")
async def chat_options():
    """Handle OPTIONS request for CORS preflight."""
    return Response(
        status_code=204,  # No Content
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS"
        }
    )

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
) -> ChatResponse:
    """
    Handle chat messages and return AI responses using Groq API.
    
    Args:
        request: Chat request containing message and conversation context
        authorization: Bearer token for authentication
        
    Returns:
        JSONResponse with AI response, conversation ID, and status
    """
    # Common response headers
    response_headers = {
        "Content-Type": "application/json",
        "Vary": "Origin"
    }
    
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    try:
        # Verify authentication
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning("Missing or invalid authorization header")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": "error",
                    "message": "Authentication required",
                    "conversation_id": conversation_id,
                    "error": "Invalid or missing authentication token"
                },
                headers=response_headers
            )
        
        # Extract token
        token = authorization.replace("Bearer ", "")
        
        # Validate request data
        if not request.message or not request.message.strip():
            error_msg = "Message cannot be empty"
            logger.warning(error_msg)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "message": error_msg,
                    "conversation_id": conversation_id,
                    "error": "Empty message"
                },
                headers=response_headers
            )
        
        # Validate personality
        if not validate_personality(request.personality):
            error_msg = f"Invalid personality: {request.personality}"
            logger.warning(error_msg)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "message": error_msg,
                    "conversation_id": conversation_id,
                    "error": "Invalid personality"
                },
                headers=response_headers
            )
        
        # Load chat history if available
        chat_history = await load_chat_history(conversation_id)
        
        # Prepare messages with personality and history
        messages = prepare_messages(
            user_message=request.message,
            personality_id=request.personality,
            chat_history=chat_history
        )
        
        # Log the request
        logger.info(f"Processing chat request for conversation: {conversation_id}")
        
        # Get response from Groq API
        try:
            logger.info(f"Sending to Groq: {request.message[:100]}...")
            response_text = await get_groq_response(messages)
            
            # Clean up the response
            response_text = response_text.strip()
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            
            logger.info(f"Successfully generated response for conversation: {conversation_id}")
            
            # Update chat history
            chat_history.extend([
                {"role": "user", "content": request.message.strip()},
                {"role": "assistant", "content": response_text}
            ])
            
            # Save updated history (async)
            await save_chat_history(conversation_id, chat_history)
            
            # Create response
            response = ChatResponse(
                message=response_text,
                conversation_id=conversation_id,
                status="success"
            )
            
            # Convert to JSONResponse to add headers
            json_response = JSONResponse(
                content=response.dict(),
                status_code=200,
                headers=cors_headers
            )
            
            return json_response
            
        except Exception as groq_error:
            error_msg = f"Groq API error: {str(groq_error)}"
            logger.error(error_msg, exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={
                    "status": "error",
                    "message": "Error processing your request",
                    "conversation_id": conversation_id,
                    "error": "Service temporarily unavailable"
                },
                headers=response_headers
            )
            
    except HTTPException as http_error:
        logger.error(f"HTTP error: {str(http_error)}")
        # Re-raise HTTPException with CORS headers
        response = JSONResponse(
            status_code=http_error.status_code,
            content={"error": str(http_error.detail)},
            headers=cors_headers
        )
        raise HTTPException(
            status_code=http_error.status_code,
            detail=http_error.detail,
            headers={"WWW-Authenticate": "Bearer"}
        ) from http_error
        
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "An unexpected error occurred",
                "conversation_id": conversation_id,
                "error": str(e)
            },
            headers=response_headers
        )
