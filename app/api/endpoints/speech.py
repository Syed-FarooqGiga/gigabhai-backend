from fastapi import APIRouter, UploadFile, File, HTTPException, status, Response
from fastapi.responses import FileResponse
from typing import Optional, Dict, Any
import os
import logging

from app.services.tts_service import TTSService
from app.services.stt_service import stt_service  # Will be updated in a separate step

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Remove the prefix since it's already added in main.py
router = APIRouter(tags=["speech"])

# Initialize TTS service
try:
    tts_service = TTSService()
    logger.info("TTS service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize TTS service: {e}")
    tts_service = None

from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str
    language: str = "en"

@router.options("/tts")
async def tts_options():
    """Handle OPTIONS request for CORS preflight."""
    response = Response()
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "600"
    return response

@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    response: Response
):
    """
    Convert text to speech in the specified language.
    
    Args:
        text: The text to convert to speech (max 500 characters)
        language: Language code (hi for Hindi, en for English, etc.)
        
    Returns:
        Audio file response with proper headers
    """
    # Set CORS headers
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    
    audio_path = None
    try:
        if not tts_service:
            logger.error("TTS service not initialized")
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"error": "TTS service is not available"}
            
        # Validate input
        if not request.text or len(request.text.strip()) == 0:
            logger.warning("Empty text received in TTS request")
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"error": "Text cannot be empty"}
            
        if len(request.text) > 500:
            logger.warning(f"Text too long: {len(request.text)} characters")
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"error": "Text is too long. Maximum 500 characters allowed."}
            
        # Generate speech
        language = request.language or "en"
        logger.info(f"Generating TTS for {len(request.text)} characters in {language}")
        
        audio_path = tts_service.generate_tts(request.text, language=language)
        
        if not audio_path or not os.path.exists(audio_path):
            logger.error(f"Failed to generate speech. Audio path: {audio_path}")
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"error": "Failed to generate speech"}
        
        # Read the audio file
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        # Create response with CORS headers
        headers = {
            "Content-Type": "audio/wav",
            "Content-Disposition": "inline; filename=speech.wav",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true"
        }
        
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers=headers,
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error in TTS endpoint: {str(e)}", exc_info=True)
        # Create a new response for errors to ensure CORS headers are set
        error_response = Response(
            content={"error": str(e)},
            media_type="application/json",
            status_code=500
        )
        error_response.headers["Access-Control-Allow-Origin"] = "*"
        error_response.headers["Access-Control-Allow-Credentials"] = "true"
        return error_response
        
    finally:
        # Clean up the temporary file if it exists
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Cleaned up temporary audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary audio file {audio_path}: {e}")
            except Exception as e:
                logger.error(f"Error cleaning up audio file {audio_path}: {str(e)}")

@router.post("/stt", response_model=Dict[str, Any])
async def speech_to_text(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = "en"
) -> Dict[str, Any]:
    """
    Convert speech to text in the specified language.
    
    Args:
        audio: Audio file to transcribe (WAV, MP3, OGG, etc.)
        language: Language code (hi for Hindi, en for English, etc.)
        
    Returns:
        Dict containing the transcribed text and metadata
    """
    # Check if audio file was provided
    if not audio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided"
        )
    
    # Validate file type
    if not audio.content_type or not audio.content_type.startswith('audio/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an audio file"
        )
    
    try:
        # Read the file content
        logger.info(f"Received audio file: {audio.filename}, size: {audio.size} bytes, type: {audio.content_type}")
        contents = await audio.read()
        
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is empty"
            )
        
        # Transcribe the audio
        logger.info(f"Transcribing audio (language: {language}, size: {len(contents)} bytes)")
        text, error_msg = await stt_service.transcribe_audio(
            audio_file=contents,
            language=language
        )
        
        if error_msg or not text:
            logger.error(f"Speech-to-text failed: {error_msg or 'No text recognized'}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "Could not transcribe audio"
            )
        
        logger.info(f"Successfully transcribed audio: {text[:100]}...")
        
        return {
            "status": "success",
            "text": text,
            "language": language,
            "audio_type": audio.content_type,
            "text_length": len(text)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error in speech-to-text: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
