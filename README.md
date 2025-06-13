# GigaBhai Backend

Backend service for GigaBhai application, built with FastAPI and Firebase.

## Features

- User authentication with Firebase Auth
- Real-time chat with Mistral AI integration
- File uploads with Firebase Storage
- Conversation history with Firestore
- Profile-based data isolation
- **Text-to-Speech (TTS)** with Coqui TTS (Hindi and English support)
- **Speech-to-Text (STT)** with OpenAI Whisper (Multi-language support)

## Prerequisites

- Python 3.8+
- Firebase project with Authentication, Firestore, and Storage services enabled
- Service account credentials from Firebase
- FFmpeg (required for Whisper STT)
- CUDA-compatible GPU (recommended for better performance)

## Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install system dependencies:
   - **Windows**: Install [FFmpeg](https://ffmpeg.org/download.html) and add it to your system PATH
   - **Linux/Debian**: `sudo apt update && sudo apt install ffmpeg`
   - **macOS**: `brew install ffmpeg`

4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Copy the example environment file and update with your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your Firebase project details and other configurations.

6. Run the development server:
   ```bash
   python start.py
   ```
   Or for production:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

## API Endpoints

### Speech

- `POST /api/speech/tts` - Convert text to speech
  - Request body: `{"text": "Your text here", "language": "hi"}`
  - Response: Audio file (WAV format)

- `POST /api/speech/stt` - Convert speech to text
  - Request: Form data with audio file
  - Response: `{"text": "Transcribed text"}`

### Authentication

- `POST /auth/signup` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh access token

## Environment Variables

- `FIREBASE_SERVICE_ACCOUNT_JSON` - Path to Firebase service account JSON file
- `FIREBASE_STORAGE_BUCKET` - Firebase Storage bucket name
- `FIREBASE_API_KEY` - Firebase Web API key
- `FIREBASE_AUTH_DOMAIN` - Firebase Auth domain
- `FIREBASE_PROJECT_ID` - Firebase Project ID
- `GROQ_API_KEY` - Groq API key for AI responses
- `MISTRAL_API_KEY` - Mistral AI API key (optional)
- `ENV` - Environment (development/production)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)

See `.env.example` for all required environment variables.

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Deployment

For production deployment, consider using:
- Google Cloud Run
- Google App Engine
- AWS Elastic Beanstalk
- Any other ASGI-compatible hosting

## License

[Your License Here]
