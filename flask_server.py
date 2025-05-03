import random
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask import request
from PIL import Image, ImageFilter
import io
from flask import send_file
import numpy as np
import json

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Set your base folder path
data_dir = Path('data')

# Image cache folder
blurred_cache_dir = Path('blurred_cache')
blurred_cache_dir.mkdir(exist_ok=True)

pixelated_cache_dir = Path('pixelated_cache')
pixelated_cache_dir.mkdir(exist_ok=True)


def pixelate_image(src_path, pixel_ratio, cache_path, pixel_map_path):
    img = Image.open(src_path).convert('RGB')
    arr = np.array(img)

    h, w, _ = arr.shape
    total_pixels = h * w
    num_visible = int(total_pixels * pixel_ratio)

    all_coords = [(i, j) for i in range(h) for j in range(w)]
    visible_coords = set(random.sample(all_coords, num_visible))

    masked_arr = np.zeros_like(arr)
    pixel_map = {}

    for i, j in visible_coords:
        masked_arr[i, j] = arr[i, j]
        pixel_map[f"{i},{j}"] = arr[i, j].tolist()

    Image.fromarray(masked_arr).save(cache_path)

    with open(pixel_map_path, 'w') as f:
        json.dump(pixel_map, f)


def blur_image(source_path, blur_level, cache_path):
    """Apply blur and save it if not already cached"""
    if not cache_path.exists():
        img = Image.open(source_path)
        blur_radius = blur_level * 2  # Adjust multiplier as needed
        blurred = img.filter(ImageFilter.GaussianBlur(blur_radius))
        blurred.save(cache_path)

def similarity_score(user_guess, actual_answer):
    # TODO module3
    if user_guess==actual_answer:
        return 0.75
    else:
        return 0.5
    # return random.uniform(0.1, 1)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    data = request.get_json()
    image_name = data.get('image_name')
    user_guess = data.get('guess', '').lower()
    mode = data.get('mode', 'blurred')
    # blur_level = data.get('blur_level', 8)

    # Extract the actual answer from image_name
    actual_answer = image_name.split('-')[0].lower()

    if similarity_score(user_guess, actual_answer) >= 0.75:
        return jsonify({'correct': True})
    if mode == 'blurred':
        blur_level = data.get('blur_level', 8)
        next_blur_level = max(blur_level - 1, 0)
        blurred_image_name = f"{image_name}_blur{next_blur_level}.jpg"
        orig_path = data_dir / actual_answer / image_name
        cache_path = blurred_cache_dir / actual_answer
        final_path = cache_path / blurred_image_name
        blur_image(orig_path, next_blur_level, final_path)

        return jsonify({
            'correct': False,
            'new_blurred_image_url': f"/blurred_image/{actual_answer}/{blurred_image_name}",
            'blur_level': next_blur_level,
            'mode': 'blurred'
        })

    elif mode == 'pixelated':
        pixel_ratio = data.get('pixel_ratio', 0.2)
        new_pixel_ratio = min(pixel_ratio + 0.1, 1.0)

        pixelated_image_name = f"{image_name}_pix{int(new_pixel_ratio*100)}.jpg"
        orig_path = data_dir / actual_answer / image_name
        cache_path = pixelated_cache_dir / actual_answer
        final_path = cache_path / pixelated_image_name
        pixel_map_path = cache_path / (pixelated_image_name + '.json')

        pixelate_image(orig_path, new_pixel_ratio, final_path, pixel_map_path)

        return jsonify({
            'correct': False,
            'new_pixelated_image_url': f"/pixelated_image/{actual_answer}/{pixelated_image_name}",
            'pixel_ratio': new_pixel_ratio,
            'mode': 'pixelated'
        })
    # else:
    #     # If incorrect guess, you could return a slightly less blurred version
    #     # For now, just returning the same image (you can improve later)

    #     # Assuming you have multiple blurred versions like abc_blur1.jpg, abc_blur2.jpg etc
    #     base_name = image_name.rsplit('.', 1)[0]  # remove .jpg
    #     extension = image_name.rsplit('.', 1)[1]

    #     # Check if image already has a blur level, like '-blur1'
    #     if 'blur' in base_name:
    #         name_parts = base_name.split('blur')
    #         blur_level = int(name_parts[1])
    #         next_blur_level = max(blur_level - 1, 0)  # decrease blur
    #         next_image_name = f"{name_parts[0]}blur{next_blur_level}.{extension}"
    #     else:
    #         # First wrong attempt, try less blur
    #         next_image_name = base_name + "blur0." + extension  # maybe no blur image
        
    #     # You can also check if the file exists before sending it, to avoid 404
    #     folder_path = data_dir / actual_answer
    #     next_image_path = folder_path / next_image_name

    #     if next_image_path.exists():
    #         return jsonify({
    #             'correct': False,
    #             'new_blurred_image_url': f"/data/{actual_answer}/{next_image_name}"
    #         })
    #     else:
    #         # If no better image exists, tell frontend to move to next
    #         return jsonify({
    #             'correct': False,
    #             'new_blurred_image_url': None
    #         })


@app.route('/random_image', methods=['GET'])
def random_image():
    # Get all subfolders (animal folders)

    mode = request.args.get('mode', 'blurred')

    animal_folders = [f for f in data_dir.iterdir() if f.is_dir()]

    # Pick a random folder
    random_folder = random.choice(animal_folders)

    # Get all image files in that folder
    image_files = [f for f in random_folder.iterdir() if f.is_file()]

    # Pick a random image
    random_image_path = random.choice(image_files)
    
    actual_answer = random_image_path.name.split('-')[0]
    image_name = random_image_path.name

    if mode == 'blurred':
        blur_level = 8  # 80% blur = level 8

        blurred_image_name = f"{image_name}_blur{blur_level}.jpg"
        cache_path = blurred_cache_dir / actual_answer
        cache_path.mkdir(parents=True, exist_ok=True)
        final_path = cache_path / blurred_image_name

        blur_image(random_image_path, blur_level, final_path)

        # Return the image file name and its folder path (you can add full URL for easy access)
        return jsonify({
            'image_name': image_name,
            'image_actual_answer': actual_answer,
            'blur_level': blur_level,
            'mode': mode,
            'image_url': f"/blurred_image/{actual_answer}/{blurred_image_name}"
        })
    
    elif mode == 'pixelated':
        pixel_ratio = 0.2  # 20% of pixels shown
        pixelated_image_name = f"{image_name}_pix{int(pixel_ratio*100)}.jpg"
        cache_path = pixelated_cache_dir / actual_answer
        cache_path.mkdir(parents=True, exist_ok=True)
        final_path = cache_path / pixelated_image_name
        pixel_map_path = cache_path / (pixelated_image_name + '.json')

        pixelate_image(random_image_path, pixel_ratio, final_path, pixel_map_path)

        return jsonify({
            'image_name': image_name,
            'image_actual_answer': actual_answer,
            'pixel_ratio': pixel_ratio,
            'mode': mode,
            'image_url': f"/pixelated_image/{actual_answer}/{pixelated_image_name}"
        })

@app.route('/data/<actual_answer>/<filename>')
def serve_image(actual_answer, filename):
    print(f"actual_answer: {actual_answer}")
    print(f"filename: {filename}")
    folder_path = data_dir / actual_answer
    return send_from_directory(folder_path, filename)

@app.route('/blurred_image/<actual_answer>/<filename>')
def serve_blurred_image(actual_answer, filename):
    folder_path = blurred_cache_dir / actual_answer
    return send_from_directory(folder_path, filename)

@app.route('/pixelated_image/<actual_answer>/<filename>')
def serve_pixelated_image(actual_answer, filename):
    folder_path = pixelated_cache_dir / actual_answer
    return send_from_directory(folder_path, filename)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Make sure the images are served under the /static route
    #app.config['UPLOAD_FOLDER'] = 'data'
    app.run(debug=True)
