import os
# import speech_recognition as sr
import traceback

# def stt(audio_file: str, language: str = "en-US") -> str:
    """
    Convert speech to text using Google's Speech Recognition.
    
    Args:
        audio_file: Path to the audio file
        language: Language code (default: "en-US")
        
    Returns:
        str: Recognized text
    """
    print("\n=== Starting STT Processing ===")
    try:
        print(f"Processing audio file: {audio_file}")
        
        # Check if file exists and has content
        if not os.path.exists(audio_file):
            raise Exception(f"Audio file not found: {audio_file}")
        
        file_size = os.path.getsize(audio_file)
        print(f"Audio file size: {file_size} bytes")
        
        if file_size == 0:
            raise Exception("Audio file is empty")

        # Initialize recognizer
        print("Initializing speech recognition...")
        recognizer = sr.Recognizer()
        
        # Read audio file
        print("Reading audio file...")
        with sr.AudioFile(audio_file) as source:
            print("Reading audio data...")
            audio = recognizer.record(source)
            print("Audio data read successfully")
        
        # Transcribe audio
        print("Transcribing...")
        text = recognizer.recognize_google(audio, language=language)
        print(f"Transcription result: {text}")
        
        return text
            
    except sr.UnknownValueError:
        print("Speech Recognition could not understand audio")
        raise Exception("Speech Recognition could not understand audio")
    except sr.RequestError as e:
        print(f"Could not request results from Speech Recognition service: {str(e)}")
        raise Exception(f"Could not request results from Speech Recognition service: {str(e)}")
    except Exception as e:
        print(f"Error in speech recognition: {str(e)}")
        print("Full error details:")
        traceback.print_exc()
        raise Exception(f"Speech recognition failed: {str(e)}")
    finally:
        # Clean up file
        try:
            if os.path.exists(audio_file):
                os.remove(audio_file)
                print(f"Cleaned up file: {audio_file}")
        except Exception as e:
            print(f"Error cleaning up file: {str(e)}")

# def stt_from_mic(language: str = "en-US") -> str:
    """
    Convert speech to text from microphone input using Google's Speech Recognition.
    
    Args:
        language: Language code (default: "en-US")
        
    Returns:
        str: Recognized text
    """
    try:
        # Initialize recognizer
        r = sr.Recognizer()
        
        # Use microphone as source
        with sr.Microphone() as source:
            print("Listening...")
            # Adjust for ambient noise
            r.adjust_for_ambient_noise(source)
            # Record audio
            audio = r.listen(source)
            
            print("Processing...")
            # Recognize speech using Google Speech Recognition
            text = r.recognize_google(audio, language=language)
            
            return text
            
    except sr.UnknownValueError:
        raise Exception("Speech Recognition could not understand audio")
    except sr.RequestError as e:
        raise Exception(f"Could not request results from Speech Recognition service: {str(e)}")
    except Exception as e:
        print(f"Error in speech recognition: {str(e)}")
        traceback.print_exc()
        raise Exception(f"Speech recognition failed: {str(e)}")

