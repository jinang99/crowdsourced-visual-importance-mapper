import os
import random
from pathlib import Path

def delete_random_90_percent(folder_path_str):
    folder_path = Path(folder_path_str)

    if not folder_path.exists() or not folder_path.is_dir():
        print(f"❌ Folder does not exist: {folder_path}")
        return

    # List all image files
    image_files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
    
    if not image_files:
        print("⚠️ No image files found in the folder.")
        return

    # Select 90% of files randomly
    num_to_delete = int(len(image_files) * 0.9)
    files_to_delete = random.sample(image_files, num_to_delete)

    # Delete selected files
    for file_path in files_to_delete:
        file_path.unlink()  # Permanently deletes the file

    print(f"✅ Deleted {num_to_delete} out of {len(image_files)} image files.")
    print(f"🗂 Remaining files: {len(image_files) - num_to_delete}")

# Example usage
delete_random_90_percent("data/cat") 
delete_random_90_percent("data/chicken") 
delete_random_90_percent("data/cow") 
delete_random_90_percent("data/dog") 
delete_random_90_percent("data/elephant") 
delete_random_90_percent("data/horse") 
delete_random_90_percent("data/sheep") 
delete_random_90_percent("data/spider") 
delete_random_90_percent("data/squirrel") 