import logging
from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.responses import JSONResponse, Response
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

@router.options("")
async def chat_options():
    """Handle OPTIONS request for CORS preflight."""
    return Response(
        status_code=204,  # No Content
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin"
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
    # Common CORS headers
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin"
    }
    
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
                },
                headers=cors_headers
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
                    "conversation_id": request.conversation_id or "",
                    "error": "Empty message"
                },
                headers=cors_headers
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
            
            # Create response with CORS headers
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
                headers=cors_headers
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
                "conversation_id": request.conversation_id if hasattr(request, 'conversation_id') else "",
                "error": "Internal server error"
            }
        )
