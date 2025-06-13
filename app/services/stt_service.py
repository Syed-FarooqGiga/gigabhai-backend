import os
import tempfile
import logging
from typing import Optional, Dict, Any, Tuple
import speech_recognition as sr
from pydub import AudioSegment
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Language mapping for speech recognition
LANGUAGE_MAP = {
    "hi": "hi-IN",  # Hindi
    "en": "en-US",  # English
    "es": "es-ES",  # Spanish
    "fr": "fr-FR",  # French
    "de": "de-DE",  # German
    "it": "it-IT",  # Italian
    "pt": "pt-BR",  # Portuguese
    "ru": "ru-RU",  # Russian
    "ja": "ja-JP",  # Japanese
    "ko": "ko-KR",  # Korean
    "zh": "zh-CN",  # Chinese (Simplified)
    "ar": "ar-EG"   # Arabic (Egypt)
}

class STTService:
    """
    Speech-to-Text service using Google's Speech Recognition.
    Converts speech from audio files to text.
    """
    
    def __init__(self):
        """Initialize the STT service."""
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  # Minimum audio energy for speech detection
        self.recognizer.pause_threshold = 0.8   # Seconds of non-speaking audio before a phrase is considered complete
        logger.info("STT Service initialized")

    async def transcribe_audio(
        self,
        audio_file: bytes,
        language: str = "en"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Transcribe audio to text.
        
        Args:
            audio_file: Audio file in bytes
            language: Language code (default: "en" for English)
            
        Returns:
            Tuple of (transcribed_text, error_message)
        """
        if not audio_file:
            return None, "No audio data provided"
            
        try:
            # Convert audio to WAV format if needed
            audio = self._convert_audio(audio_file)
            if not audio:
                return None, "Unsupported audio format"
            
            # Save to a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                audio.export(temp_file.name, format="wav")
                temp_path = temp_file.name
            
            try:
                # Use the audio file as the audio source
                with sr.AudioFile(temp_path) as source:
                    # Adjust for ambient noise
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Listen for the data (load audio to memory)
                    audio_data = self.recognizer.record(source)
                    
                    # Get the language code, default to English if not found
                    lang_code = LANGUAGE_MAP.get(language.lower().strip(), "en-US")
                    
                    logger.info(f"Transcribing audio (language: {lang_code}, size: {len(audio_file)} bytes)")
                    
                    # Recognize speech using Google Speech Recognition
                    text = self.recognizer.recognize_google(
                        audio_data,
                        language=lang_code
                    )
                    
                    logger.info(f"Successfully transcribed audio: {text[:100]}...")
                    return text, None
                    
            except sr.UnknownValueError:
                error_msg = "Google Speech Recognition could not understand the audio"
                logger.warning(error_msg)
                return None, error_msg
                
            except sr.RequestError as e:
                error_msg = f"Could not request results from Google Speech Recognition service: {e}"
                logger.error(error_msg)
                return None, error_msg
                
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Could not remove temporary file {temp_path}: {e}")
                    
        except Exception as e:
            error_msg = f"Error in transcribe_audio: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    def _convert_audio(self, audio_data: bytes) -> Optional[AudioSegment]:
        """
        Convert audio data to a format compatible with speech recognition.
        
        Args:
            audio_data: Raw audio data in various formats
            
        Returns:
            AudioSegment object or None if conversion fails
        """
        try:
            # Try to detect the format from the data
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to mono, 16kHz, 16-bit PCM
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(16000)
            audio = audio.set_sample_width(2)
            
            return audio
            
        except Exception as e:
            logger.error(f"Error converting audio: {str(e)}")
            return None

# Create a singleton instance
stt_service = STTService()
