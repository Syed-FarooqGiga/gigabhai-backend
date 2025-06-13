# Speech Services

This directory contains the Text-to-Speech (TTS) and Speech-to-Text (STT) services for the GigaBhai application.

## Text-to-Speech (TTS) Service

The TTS service converts text to speech using gTTS (Google Text-to-Speech).

### Features
- Supports multiple languages (Hindi, English, Spanish, etc.)
- Converts text to WAV format
- Handles long text by splitting into chunks
- Caches generated audio files

### Usage

```python
from app.services.tts_service import TTSService

# Initialize the service
tts_service = TTSService(output_dir="path/to/output")

# Generate speech
output_path = await tts_service.generate_tts(
    text="Hello, world!",
    language="en"  # Language code (en, hi, es, etc.)
)
```

### API Endpoint

```
POST /api/speech/tts
Content-Type: application/json

{
    "text": "Hello, world!",
    "language": "en"
}
```

## Speech-to-Text (STT) Service

The STT service converts speech to text using Google's Speech Recognition API.

### Features
- Supports multiple languages
- Handles various audio formats (WAV, MP3, etc.)
- Automatic audio format conversion
- Configurable recognition settings

### Usage

```python
from app.services.stt_service import STTService

# Initialize the service
stt_service = STTService()

# Transcribe audio
with open("audio.wav", "rb") as f:
    audio_data = f.read()

text, error = await stt_service.transcribe_audio(
    audio_file=audio_data,
    language="en"  # Language code (en, hi, es, etc.)
)
```

### API Endpoint

```
POST /api/speech/stt
Content-Type: multipart/form-data

{
    "audio": <binary audio file>,
    "language": "en"
}
```

## Supported Languages

| Language | Code |
|----------|------|
| English | en |
| Hindi | hi |
| Spanish | es |
| French | fr |
| German | de |
| Italian | it |
| Portuguese | pt |
| Russian | ru |
| Japanese | ja |
| Korean | ko |
| Chinese (Simplified) | zh |
| Arabic | ar |

## Dependencies

- gTTS (Google Text-to-Speech)
- SpeechRecognition
- pydub
- ffmpeg

## Testing

Run the test script to verify the services:

```bash
python -m tests.test_speech_services
```

## Notes

- For STT to work properly, ensure FFmpeg is installed and available in your system PATH.
- The TTS service requires an internet connection to generate speech.
- Audio files are cached in the specified output directory.
