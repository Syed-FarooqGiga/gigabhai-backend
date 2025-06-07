# GigaBhai Backend

Backend service for GigaBhai application, built with FastAPI and Firebase.

## Features

- User authentication with Firebase Auth
- Real-time chat with Mistral AI integration
- File uploads with Firebase Storage
- Conversation history with Firestore
- Profile-based data isolation

## Prerequisites

- Python 3.8+
- Firebase project with Authentication, Firestore, and Storage services enabled
- Service account credentials from Firebase

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

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the example environment file and update with your Firebase credentials:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your Firebase project details.

5. Run the development server:
   ```bash
   uvicorn main:app --reload
   ```

## Environment Variables

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
