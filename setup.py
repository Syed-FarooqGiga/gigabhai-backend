import subprocess
import sys
import os
from pathlib import Path

def run_command(command):
    try:
        subprocess.run(command, check=True, shell=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error: {str(e)}")
        return False

def setup_backend():
    print("Setting up GigaBhai backend...")
    
    # Create virtual environment if it doesn't exist
    if not os.path.exists('venv'):
        print("Creating virtual environment...")
        if not run_command(f"{sys.executable} -m venv venv"):
            return False
    
    # Activate virtual environment and install dependencies
    if sys.platform == 'win32':
        activate_cmd = "venv\\Scripts\\activate"
        pip_cmd = "venv\\Scripts\\pip"
    else:
        activate_cmd = "source venv/bin/activate"
        pip_cmd = "venv/bin/pip"
    
    print("Installing dependencies...")
    if not run_command(f"{pip_cmd} install -r requirements.txt"):
        return False
    
    # Download Vosk models
    print("Downloading speech recognition models...")
    if not run_command(f"{pip_cmd} install tqdm requests"):
        return False
    
    if not run_command(f"{sys.executable} download_models.py"):
        return False
    
    print("\nBackend setup completed successfully!")
    print("\nTo start the backend server:")
    if sys.platform == 'win32':
        print("venv\\Scripts\\activate")
        print("uvicorn main:app --reload")
    else:
        print("source venv/bin/activate")
        print("uvicorn main:app --reload")
    
    return True

if __name__ == "__main__":
    setup_backend() 