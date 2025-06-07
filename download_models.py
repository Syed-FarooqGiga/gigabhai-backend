import os
import requests
import zipfile
import shutil
from tqdm import tqdm

def download_file(url: str, filename: str):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as f, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as pbar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            pbar.update(size)

def download_vosk_models():
    # Create models directory if it doesn't exist
    os.makedirs('models', exist_ok=True)
    
    # Model URLs
    models = {
        'en': 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',
        'hi': 'https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip'
    }
    
    for lang, url in models.items():
        model_dir = f'models/vosk-model-small-{lang}'
        if os.path.exists(model_dir):
            print(f"Model for {lang} already exists, skipping...")
            continue
            
        print(f"Downloading {lang} model...")
        zip_file = f'models/vosk-model-small-{lang}.zip'
        download_file(url, zip_file)
        
        print(f"Extracting {lang} model...")
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall('models')
            
        # Clean up zip file
        os.remove(zip_file)
        
        # Rename extracted directory to match our expected path
        extracted_dir = os.listdir('models')[0]  # Get the first directory
        if extracted_dir != f'vosk-model-small-{lang}':
            shutil.move(os.path.join('models', extracted_dir), model_dir)
    
    print("All models downloaded and extracted successfully!")

if __name__ == '__main__':
    download_vosk_models() 