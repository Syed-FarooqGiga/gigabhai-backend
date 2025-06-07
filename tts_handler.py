# import pyttsx3
# from gtts import gTTS
import os
import tempfile

# Initialize pyttsx3 engine
# engine = pyttsx3.init()

# Set properties for pyttsx3
# def set_voice_properties(engine, personality):
#     voices = engine.getProperty('voices')
#     
#     # Set voice based on personality
#     if personality == 'swag':
#         # Try to find a young male voice
#         for voice in voices:
#             if 'male' in voice.name.lower():
#                 engine.setProperty('voice', voice.id)
#                 break
#         engine.setProperty('rate', 180)  # Slightly faster for swag
#     elif personality == 'ceo':
#         # Try to find a mature male voice
#         for voice in voices:
#             if 'male' in voice.name.lower():
#                 engine.setProperty('voice', voice.id)
#                 break
#         engine.setProperty('rate', 150)  # Slower for CEO
#     elif personality == 'roast':
#         # Try to find a young male voice
#         for voice in voices:
#             if 'male' in voice.name.lower():
#                 engine.setProperty('voice', voice.id)
#                 break
#         engine.setProperty('rate', 170)  # Medium-fast for roasts
#     elif personality == 'vidhyarthi':
#         # Try to find a young voice
#         for voice in voices:
#             if 'young' in voice.name.lower():
#                 engine.setProperty('voice', voice.id)
#                 break
#         engine.setProperty('rate', 160)  # Medium for student
#     else:  # jugadu
#         # Try to find a mature male voice
#         for voice in voices:
#             if 'male' in voice.name.lower():
#                 engine.setProperty('voice', voice.id)
#                 break
#         engine.setProperty('rate', 155)  # Medium-slow for jugaad

# Text-to-Speech function using pyttsx3 (works offline)
# def speak_pyttsx3(text: str, personality: str):
#     try:
#         set_voice_properties(engine, personality)
#         engine.say(text)
#         engine.runAndWait()
#         return True
#     except Exception as e:
#         print(f"Error in pyttsx3 TTS: {str(e)}")
#         return False

# Text-to-Speech function using gTTS (works online, supports multiple languages)
# def speak_gtts(text: str, language='en'):
#     try:
#         # Remove region suffix if present (e.g. hi-IN -> hi)
#         lang_code = language.split('-')[0]
#         tts = gTTS(text=text, lang=lang_code, slow=False)
#         
#         # Create a temporary file
#         with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
#             temp_filename = fp.name
#             
#         # Save the audio file
#         tts.save(temp_filename)
#         
#         # Play the audio file
#         os.system(f'start {temp_filename}')  # Windows
#         # For Linux: os.system(f'xdg-open {temp_filename}')
#         # For Mac: os.system(f'open {temp_filename}')
#         
#         # Clean up after a delay
#         import threading
#         def cleanup():
#             import time
#             time.sleep(5)  # Wait for audio to finish playing
#             os.remove(temp_filename)
#         
#         threading.Thread(target=cleanup).start()
#         return True
#     except Exception as e:
#         print(f"Error in gTTS: {str(e)}")
#         return False

# Main TTS function that tries pyttsx3 first, falls back to gTTS
# def speak(text: str, personality: str):
#     # Try pyttsx3 first (offline)
#     if speak_pyttsx3(text, personality):
#         return True
#         
#     # Fall back to gTTS if pyttsx3 fails
#     return speak_gtts(text)
