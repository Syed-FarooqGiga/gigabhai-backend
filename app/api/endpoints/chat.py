import logging
from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
from groq_handler import get_groq_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

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

# Personality system prompts
PERSONALITY_PROMPTS = {
    'swag_bhai': (
        "You are Swag Bhai, a cool and friendly assistant who speaks in a hip, casual style with emojis. "
        "You're helpful, witty, and always keep it real. Use modern slang and keep responses concise and engaging. "
        "Use emojis to express emotions and keep the tone light and fun."
    ),
    'default': (
        "You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, "
        "while being safe. Your answers should not include any harmful, unethical, racist, sexist, "
        "toxic, dangerous, or illegal content. Please ensure that your responses are socially "
        "unbiased and positive in nature."
    )
}

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
    try:
        # Verify authentication
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning("Missing or invalid authorization header")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "status": "error",
                    "message": "Authentication required",
                    "conversation_id": request.conversation_id or "",
                    "error": "Invalid or missing authentication token"
                }
            )
            
        # Extract token
        token = authorization.replace("Bearer ", "")
        
        # Validate request data
        if not request.message or not request.message.strip():
            logger.warning("Empty message received")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "message": "Message cannot be empty",
                    "conversation_id": request.conversation_id or "",
                    "error": "Empty message"
                }
            )
        
        # Get the system prompt based on personality
        personality = request.personality.lower()
        system_prompt = PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS['default'])
        
        # Prepare messages for the API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history if available
        if request.chat_history:
            messages.extend(request.chat_history)
        
        # Add the current user message
        messages.append({"role": "user", "content": request.message.strip()})
        
        # Generate conversation ID if new conversation
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
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
            
            return ChatResponse(
                message=response_text,
                conversation_id=conversation_id,
                status="success"
            )
            
        except Exception as groq_error:
            logger.error(f"Groq API error: {str(groq_error)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={
                    "status": "error",
                    "message": "Error processing your request",
                    "conversation_id": conversation_id,
                    "error": "Service temporarily unavailable"
                }
            )
            
    except HTTPException as http_error:
        logger.error(f"HTTP error: {str(http_error)}")
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "An unexpected error occurred",
                "conversation_id": request.conversation_id if hasattr(request, 'conversation_id') else "",
                "error": "Internal server error"
            }
        )
