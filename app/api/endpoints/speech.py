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

@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    response: Response
) -> Response:
    """
    Convert text to speech in the specified language.
    
    Args:
        text: The text to convert to speech (max 500 characters)
        language: Language code (hi for Hindi, en for English, etc.)
        
    Returns:
        Audio file response with proper headers
    """
    text = request.text
    language = request.language
    
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text provided for TTS conversion"
        )
    
    # Limit text length to prevent abuse
    if len(text) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text too long. Maximum 500 characters allowed."
        )
    
    # Check if TTS service is available
    if tts_service is None:
        logger.error("TTS service is not available")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text-to-speech service is currently unavailable"
        )
    
    try:
        # Generate speech
        logger.info(f"Generating speech for text (language: {language}, length: {len(text)})")
        
        # Use the TTS service to generate the audio file
        audio_path, error_msg = await tts_service.text_to_speech(text, language)
        
        if error_msg or not audio_path or not os.path.exists(audio_path):
            logger.error(f"Failed to generate TTS: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate speech: {error_msg or 'Unknown error'}"
            )
        
        # Read the audio file
        with open(audio_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        # Clean up the temporary file
        try:
            os.remove(audio_path)
        except Exception as e:
            logger.warning(f"Could not remove temporary audio file: {e}")
        
        # Return the audio file directly
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in TTS endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request: {str(e)}"
        )

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
