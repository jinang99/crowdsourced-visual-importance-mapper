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
import spacy
from functools import lru_cache
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import process


app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Set your base folder path
data_dir = Path("data")
city_data_dir = Path("city_data")

# Image cache folder
blurred_cache_dir = Path("blurred_cache")
blurred_cache_dir.mkdir(exist_ok=True)

pixelated_cache_dir = Path("pixelated_cache")
pixelated_cache_dir.mkdir(exist_ok=True)


known_labels = ['mumbai', 'delhi', 'kuala lumpur', 'berlin', 'hyderabad', 'chicago', 'orlando', 'paris', 'san francisco',
                'butterfly', 'spider', 'cow', 'dog', 'chicken', 'elephant', 'horse', 'sheep', 'squirrel']

# Load spaCy model with error handling
try:
    nlp = spacy.load("en_core_web_md")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
    nlp = spacy.load("en_core_web_md")

# Load SentenceTransformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

def correct_typo(user_input, label_list, threshold=85):
    match, score, _ = process.extractOne(user_input, label_list)
    if score >= threshold:
        return match
    return user_input 


def pixelate_image(
    src_path, pixel_ratio, cache_path, pixel_map_path, prev_visible_coords=None
):
    img = Image.open(src_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    total_pixels = h * w
    num_visible = int(total_pixels * pixel_ratio)

    all_coords = [(i, j) for i in range(h) for j in range(w)]

    # Create full pixel map once
    full_pixel_map = {f"{i},{j}": arr[i, j].tolist() for i, j in all_coords}

    if prev_visible_coords is None:
        visible_coords = set(random.sample(all_coords, num_visible))
    else:
        hidden_coords = list(set(all_coords) - set(prev_visible_coords))
        needed_more = num_visible - len(prev_visible_coords)
        if needed_more > 0:
            newly_revealed = set(random.sample(hidden_coords, needed_more))
            visible_coords = set(prev_visible_coords) | newly_revealed
        else:
            visible_coords = set(prev_visible_coords)

    # Create a masked image using full map + visibility info
    masked_arr = np.zeros_like(arr)
    for i, j in visible_coords:
        masked_arr[i, j] = arr[i, j]

    Image.fromarray(masked_arr).save(cache_path)

    with open(pixel_map_path, "w") as f:
        json.dump(
            {
                "visible_coords": list(map(list, visible_coords)),
                "pixel_map": full_pixel_map,
            },
            f,
        )

# def pixelate_image_blockwise(
#     src_path,
#     pixel_ratio,
#     cache_path,
#     pixel_map_path,
#     prev_visible_blocks=None,
#     block_size=12,
# ):
#     img = Image.open(src_path).convert("RGB")
#     arr = np.array(img)
#     h, w, _ = arr.shape

#     # Make sure image dims are multiples of block_size (pad if needed)
#     pad_h = (block_size - h % block_size) % block_size
#     pad_w = (block_size - w % block_size) % block_size
#     arr = np.pad(arr, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant")
#     h, w, _ = arr.shape

#     blocks_h = h // block_size
#     blocks_w = w // block_size
#     total_blocks = blocks_h * blocks_w
#     num_visible_blocks = int(total_blocks * pixel_ratio)

#     all_blocks = [(i, j) for i in range(blocks_h) for j in range(blocks_w)]

#     if prev_visible_blocks is None:
#         visible_blocks = set(random.sample(all_blocks, num_visible_blocks))
#     else:
#         hidden_blocks = list(set(all_blocks) - set(prev_visible_blocks))
#         needed_more = num_visible_blocks - len(prev_visible_blocks)
#         newly_revealed = (
#             set(random.sample(hidden_blocks, needed_more)) if needed_more > 0 else set()
#         )
#         visible_blocks = set(prev_visible_blocks) | newly_revealed

#     # Masked array
#     masked_arr = np.zeros_like(arr)
#     for bi, bj in visible_blocks:
#         i_start, i_end = bi * block_size, (bi + 1) * block_size
#         j_start, j_end = bj * block_size, (bj + 1) * block_size
#         masked_arr[i_start:i_end, j_start:j_end] = arr[i_start:i_end, j_start:j_end]

#     Image.fromarray(masked_arr[: h - pad_h or None, : w - pad_w or None]).save(
#         cache_path
#     )

#     # Save full pixel map + visible blocks
#     full_pixel_map = {
#         f"{i},{j}": arr[i, j].tolist() for i in range(h) for j in range(w)
#     }

#     with open(pixel_map_path, "w") as f:
#         json.dump(
#             {
#                 "visible_blocks": list(map(list, visible_blocks)),  # [[bi, bj], ...]
#                 "block_size": block_size,
#                 "pixel_map": full_pixel_map,
#                 "original_shape": [h - pad_h, w - pad_w],
#             },
#             f,
#         )


def pixelate_image_blockwise(
    src_path,
    pixel_ratio,
    cache_path,
    pixel_map_path,
    prev_visible_blocks=None,
    block_size=12,
):
    img = Image.open(src_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape

    # Pad image to make dimensions divisible by block_size
    pad_h = (block_size - h % block_size) % block_size
    pad_w = (block_size - w % block_size) % block_size
    arr = np.pad(arr, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant")
    h, w, _ = arr.shape

    blocks_h = h // block_size
    blocks_w = w // block_size
    total_blocks = blocks_h * blocks_w
    num_visible_blocks = int(total_blocks * pixel_ratio)

    # --- Neighbor logic (4-connected) ---
    def get_adjacent_blocks(block, max_h, max_w):
        i, j = block
        neighbors = []
        for di, dj in [(-1,0), (1,0), (0,-1), (0,1)]:
            ni, nj = i + di, j + dj
            if 0 <= ni < max_h and 0 <= nj < max_w:
                neighbors.append((ni, nj))
        return neighbors

    # --- Determine visible blocks ---
    if prev_visible_blocks is None:
        all_blocks = [(i, j) for i in range(blocks_h) for j in range(blocks_w)]
        seed = random.choice(all_blocks)  
        visible_blocks = {seed}
    else:
        visible_blocks = set(prev_visible_blocks)

    # BFS-like expansion
    to_visit = list(visible_blocks)
    visited = set(visible_blocks)
    while len(visible_blocks) < num_visible_blocks and to_visit:
        current = to_visit.pop(0)
        for neighbor in get_adjacent_blocks(current, blocks_h, blocks_w):
            if neighbor not in visited:
                visible_blocks.add(neighbor)
                to_visit.append(neighbor)
                visited.add(neighbor)
            if len(visible_blocks) >= num_visible_blocks:
                break

    # --- Mask image array ---
    masked_arr = np.zeros_like(arr)
    for bi, bj in visible_blocks:
        i_start, i_end = bi * block_size, (bi + 1) * block_size
        j_start, j_end = bj * block_size, (bj + 1) * block_size
        masked_arr[i_start:i_end, j_start:j_end] = arr[i_start:i_end, j_start:j_end]

    # Save image
    masked_crop = masked_arr[: h - pad_h or None, : w - pad_w or None]
    Image.fromarray(masked_crop).save(cache_path)

    # --- Save metadata ---
    full_pixel_map = {
        f"{i},{j}": arr[i, j].tolist() for i in range(h) for j in range(w)
    }

    with open(pixel_map_path, "w") as f:
        json.dump(
            {
                "visible_blocks": list(map(list, visible_blocks)),
                "block_size": block_size,
                "pixel_map": full_pixel_map,
                "original_shape": [h - pad_h, w - pad_w],
            },
            f,
        )


def blur_image(source_path, blur_level, cache_path):
    """Apply blur and save it if not already cached"""
    if not cache_path.exists():
        img = Image.open(source_path)
        blur_radius = blur_level * 2  # Adjust multiplier as needed
        blurred = img.filter(ImageFilter.GaussianBlur(blur_radius))
        blurred.save(cache_path)

def similarity_score(user_guess, actual_answer, model):
    """Calculate semantic similarity score (0-1) using sentence-transformers"""
    try:
        emb1 = model.encode(correct_typo(user_guess.lower().strip(), known_labels), convert_to_tensor=True)
        print(correct_typo(user_guess.lower().strip(), known_labels))
        emb2 = model.encode(actual_answer.lower().strip(), convert_to_tensor=True)
        similarity = util.pytorch_cos_sim(emb1, emb2)
        return similarity.item()
    except Exception as e:
        print(f"Similarity calculation failed: {e}")
        return 0.0  # Fallback value if something goes wrong


@app.route("/check_answer", methods=["POST"])
def check_answer():
    data = request.get_json()
    domain = data.get("domain", "animals")
    base_dir = data_dir if domain == "animals" else city_data_dir
    image_name = data.get("image_name")
    user_guess = data.get("guess", "").lower()
    mode = data.get("mode", "blurred")
    # blur_level = data.get('blur_level', 8)

    # Extract the actual answer from image_name
    actual_answer = image_name.split("-")[0].lower()


    sim_score = similarity_score(user_guess, actual_answer, model)
    print(sim_score)

    if sim_score >= 0.75:
        return jsonify({"correct": True})
    
    if mode == "blurred":
        blur_level = data.get("blur_level", 8)
        next_blur_level = max(blur_level - 1, 0)
        if next_blur_level == 0:
            # Image is fully revealed — move to next one
            return jsonify({
                "correct": False,
                "move_to_next": True
            })
        blurred_image_name = f"{image_name}_blur{next_blur_level}.jpg"
        orig_path = base_dir / actual_answer / image_name
        cache_path = blurred_cache_dir / actual_answer
        final_path = cache_path / blurred_image_name
        blur_image(orig_path, next_blur_level, final_path)

        return jsonify(
            {
                "correct": False,
                "new_blurred_image_url": f"/blurred_image/{actual_answer}/{blurred_image_name}",
                "blur_level": next_blur_level,
                "mode": "blurred", 
                "similarity_score": sim_score,
            }
        )

    elif mode == "pixelated":
        pixel_ratio = round(data.get("pixel_ratio", 0.1), 2)
        new_pixel_ratio = min(pixel_ratio + 0.05, 1.0)
        if new_pixel_ratio >= 1.0:
            # Image is fully revealed — move to next one
            return jsonify({
                "correct": False,
                "move_to_next": True
            })

        pixelated_image_name = f"{image_name}_pix{int(new_pixel_ratio*100)}.jpg"
        orig_path = base_dir / actual_answer / image_name
        cache_path = pixelated_cache_dir / actual_answer
        final_path = cache_path / pixelated_image_name
        pixel_map_path = cache_path / (pixelated_image_name + ".json")

        prev_pixel_ratio = round(pixel_ratio, 2)
        prev_image_name = f"{image_name}_pix{int(prev_pixel_ratio*100)}.jpg"
        prev_pixel_map_path = cache_path / (prev_image_name + ".json")

        prev_visible_blocks = None
        with open(prev_pixel_map_path, "r") as f:
            data = json.load(f)
            prev_visible_blocks = [
                tuple(coord) for coord in data.get("visible_blocks", [])
            ]

        pixelate_image_blockwise(
            orig_path, new_pixel_ratio, final_path, pixel_map_path, prev_visible_blocks
        )

        return jsonify(
            {
                "correct": False,
                "new_pixelated_image_url": f"/pixelated_image/{actual_answer}/{pixelated_image_name}",
                "pixel_ratio": new_pixel_ratio,
                "mode": "pixelated",
                "similarity_score": sim_score,
            }
        )


@app.route("/random_image", methods=["GET"])
def random_image():
    # Get all subfolders (animal folders)

    mode = request.args.get("mode", "blurred")

    domain = request.args.get("domain", "animals")
    base_dir = data_dir if domain == "animals" else city_data_dir
    folders = [f for f in base_dir.iterdir() if f.is_dir()]

    # Pick a random folder
    random_folder = random.choice(folders)

    # Get all image files in that folder
    image_files = [f for f in random_folder.iterdir() if f.is_file()]

    # Pick a random image
    random_image_path = random.choice(image_files)

    actual_answer = random_image_path.name.split("-")[0]
    image_name = random_image_path.name

    if mode == "blurred":
        blur_level = 8  # 80% blur = level 8

        blurred_image_name = f"{image_name}_blur{blur_level}.jpg"
        cache_path = blurred_cache_dir / actual_answer
        cache_path.mkdir(parents=True, exist_ok=True)
        final_path = cache_path / blurred_image_name

        blur_image(random_image_path, blur_level, final_path)

        # Return the image file name and its folder path (you can add full URL for easy access)
        return jsonify(
            {
                "image_name": image_name,
                "image_actual_answer": actual_answer,
                "blur_level": blur_level,
                "mode": mode,
                "image_url": f"/blurred_image/{actual_answer}/{blurred_image_name}",
            }
        )

    elif mode == "pixelated":
        pixel_ratio = 0.1  # 20% of pixels shown
        pixelated_image_name = f"{image_name}_pix{int(pixel_ratio*100)}.jpg"
        cache_path = pixelated_cache_dir / actual_answer
        cache_path.mkdir(parents=True, exist_ok=True)
        final_path = cache_path / pixelated_image_name
        pixel_map_path = cache_path / (pixelated_image_name + ".json")

        pixelate_image_blockwise(
            random_image_path,
            pixel_ratio,
            final_path,
            pixel_map_path,
            prev_visible_blocks=None,
        )

        return jsonify(
            {
                "image_name": image_name,
                "image_actual_answer": actual_answer,
                "pixel_ratio": pixel_ratio,
                "mode": mode,
                "image_url": f"/pixelated_image/{actual_answer}/{pixelated_image_name}",
            }
        )


@app.route("/data/<actual_answer>/<filename>")
def serve_image(actual_answer, filename):
    print(f"actual_answer: {actual_answer}")
    print(f"filename: {filename}")
    folder_path = data_dir / actual_answer
    return send_from_directory(folder_path, filename)


@app.route("/blurred_image/<actual_answer>/<filename>")
def serve_blurred_image(actual_answer, filename):
    folder_path = blurred_cache_dir / actual_answer
    return send_from_directory(folder_path, filename)


@app.route("/pixelated_image/<actual_answer>/<filename>")
def serve_pixelated_image(actual_answer, filename):
    folder_path = pixelated_cache_dir / actual_answer
    return send_from_directory(folder_path, filename)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # Make sure the images are served under the /static route
    # app.config['UPLOAD_FOLDER'] = 'data'
    app.run(debug=True)
