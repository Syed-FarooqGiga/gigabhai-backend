import os
import time
from typing import Optional, Tuple
import logging
from pathlib import Path
from gtts import gTTS
from pydub import AudioSegment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create output directory if it doesn't exist
LANGUAGE_MAP = {
    "hi": "hi",  # Hindi
    "en": "en",  # English
    "es": "es",  # Spanish
    "fr": "fr",  # French
    "de": "de",  # German
    "it": "it",  # Italian
    "pt": "pt",  # Portuguese
    "ru": "ru",  # Russian
    "ja": "ja",  # Japanese
    "ko": "ko",  # Korean
    "zh": "zh-CN",  # Chinese (Simplified)
    "ar": "ar"   # Arabic
}

class TTSService:
    """
    Text-to-Speech service using gTTS (Google Text-to-Speech).
    Converts text to speech and saves it as a WAV file.
    """
    
    def __init__(self, output_dir: str = "tts_output"):
        """
        Initialize the TTS service.
        
        Args:
            output_dir: Directory to save the generated audio files
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"TTS Service initialized. Output directory: {os.path.abspath(self.output_dir)}")

    async def text_to_speech(
        self, 
        text: str, 
        language: str = "en"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Convert text to speech using gTTS and save as WAV file.
        
        Args:
            text: Text to convert to speech
            language: Language code (default: "en" for English)
        
        Returns:
            Tuple of (file_path, error_message)
        """
        if not text or not text.strip():
            return None, "No text provided"
        
        try:
            # Generate a unique filename
            timestamp = int(time.time())
            mp3_filename = os.path.join(self.output_dir, f"output_{timestamp}.mp3")
            wav_filename = os.path.join(self.output_dir, f"output_{timestamp}.wav")
            
            # Get the language code, default to English if not found
            lang_code = LANGUAGE_MAP.get(language.lower().strip(), "en")
            
            logger.info(f"Generating TTS for text (language: {lang_code}, length: {len(text)} chars)")
            
            # Create gTTS object and save as MP3
            tts = gTTS(text=text, lang=lang_code, slow=False)
            tts.save(mp3_filename)
            
            # Convert MP3 to WAV using pydub
            audio = AudioSegment.from_mp3(mp3_filename)
            audio.export(wav_filename, format="wav")
            
            # Clean up the temporary MP3 file
            try:
                os.remove(mp3_filename)
            except Exception as e:
                logger.warning(f"Could not remove temporary MP3 file: {e}")
            
            logger.info(f"TTS generated successfully: {wav_filename}")
            return wav_filename, None
            
        except Exception as e:
            error_msg = f"Error in text_to_speech: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg

    async def generate_tts(
        self, 
        text: str, 
        language: str = "en",
        output_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate speech from text and save as WAV file.
        
        Args:
            text: Text to convert to speech
            language: Language code (default: "en" for English)
            output_dir: Optional directory to override the default output directory
            
        Returns:
            Path to the generated audio file or None if generation failed
        """
        output_dir = output_dir or self.output_dir
        file_path, error_msg = await self.text_to_speech(text, language)
        
        if error_msg:
            logger.error(f"Failed to generate TTS: {error_msg}")
            return None
            
        return file_path

# Create a singleton instance
tts_service = TTSService()
