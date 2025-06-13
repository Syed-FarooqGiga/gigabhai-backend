import os
import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tts_service import TTSService
from app.services.stt_service import STTService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test text for TTS
TEST_TEXTS = {
    "en": "Hello, this is a test of the text-to-speech service.",
    "hi": "नमस्ते, यह टेक्स्ट-टू-स्पीच सेवा का परीक्षण है।",
    "es": "Hola, esta es una prueba del servicio de texto a voz.",
}

# Audio file for STT test
TEST_AUDIO_FILE = "test_audio.wav"

async def test_tts_service():
    """Test the Text-to-Speech service with different languages."""
    logger.info("Testing TTS Service...")
    
    tts_service = TTSService()
    
    for lang, text in TEST_TEXTS.items():
        try:
            logger.info(f"Testing TTS with language: {lang}")
            output_path = await tts_service.generate_tts(
                text=text,
                language=lang
            )
            
            if output_path and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(f"Success! Generated {lang} audio: {output_path} ({file_size} bytes)")
                
                # Save the first audio file for STT testing
                if lang == "en" and not os.path.exists(TEST_AUDIO_FILE):
                    import shutil
                    shutil.copy2(output_path, TEST_AUDIO_FILE)
                    logger.info(f"Copied test audio to {TEST_AUDIO_FILE}")
            else:
                logger.error(f"Failed to generate {lang} audio")
                
        except Exception as e:
            logger.error(f"Error testing {lang} TTS: {str(e)}", exc_info=True)

async def test_stt_service():
    """Test the Speech-to-Text service."""
    logger.info("\nTesting STT Service...")
    
    if not os.path.exists(TEST_AUDIO_FILE):
        logger.warning(f"Test audio file not found: {TEST_AUDIO_FILE}")
        logger.info("Skipping STT test. Please run TTS test first to generate test audio.")
        return
    
    stt_service = STTService()
    
    try:
        with open(TEST_AUDIO_FILE, "rb") as f:
            audio_data = f.read()
        
        logger.info(f"Testing STT with audio file: {TEST_AUDIO_FILE} ({len(audio_data)} bytes)")
        
        # Test with English
        text, error = await stt_service.transcribe_audio(
            audio_file=audio_data,
            language="en"
        )
        
        if text:
            logger.info(f"STT Result (en): {text}")
        else:
            logger.error(f"STT failed: {error}")
            
    except Exception as e:
        logger.error(f"Error testing STT: {str(e)}", exc_info=True)

async def main():
    """Run all tests."""
    logger.info("Starting speech service tests...")
    
    # Test TTS first to generate audio for STT testing
    await test_tts_service()
    
    # Then test STT with the generated audio
    await test_stt_service()
    
    logger.info("\nTest completed!")

if __name__ == "__main__":
    asyncio.run(main())
