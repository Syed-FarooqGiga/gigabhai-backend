import logging
from fastapi import APIRouter, HTTPException, status, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
from groq_handler import get_groq_response

# Configure logging
logging.basicConfig(level=logging.INFO)
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
):
    """
    Handle chat messages and return AI responses using Groq API.
    
    Args:
        request: Chat request containing message and conversation context
        
    Returns:
        ChatResponse with AI response and conversation ID
    """
    try:
        # Verify authentication
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authentication token"
            )
            
        # Extract token (you would verify this token in a real app)
        token = authorization.replace("Bearer ", "")
        
        # Extract data from request
        message = request.message.strip()
        personality = request.personality.lower()
        conversation_id = request.conversation_id
        chat_history = request.chat_history or []
        
        logger.info(f"Received chat request from user {request.user_id}")
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty"
            )
        
        # Get the system prompt based on personality
        system_prompt = PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS['default'])
        
        # Prepare messages for the API
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add chat history if available
        if chat_history:
            messages.extend(chat_history)
        
        # Add the current user message
        messages.append({"role": "user", "content": message})
        
        # Get response from Groq API
        logger.info(f"Sending to Groq: {message[:100]}...")
        response_text = await get_groq_response(messages)
        
        # Clean up the response
        response_text = response_text.strip()
        if response_text.startswith('"') and response_text.endswith('"'):
            response_text = response_text[1:-1]
        
        # If this is a new conversation, generate a conversation ID
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        logger.info(f"Generated response: {response_text[:100]}...")
        
        return ChatResponse(
            message=response_text,
            conversation_id=conversation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        logger.error(error_detail)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )
