import random
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask import request


app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Set your base folder path
data_dir = Path('data')

def similarity_score(user_guess, actual_answer):
    # TODO module3
    return random.uniform(0.5, 1)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    data = request.get_json()
    image_name = data.get('image_name')
    user_guess = data.get('guess', '').lower()

    # Extract the actual answer from image_name
    actual_answer = image_name.split('-')[0].lower()

    if similarity_score(user_guess, actual_answer) >= 0.75:
        return jsonify({'correct': True})
    else:
        # If incorrect guess, you could return a slightly less blurred version
        # For now, just returning the same image (you can improve later)

        # Assuming you have multiple blurred versions like abc_blur1.jpg, abc_blur2.jpg etc
        base_name = image_name.rsplit('.', 1)[0]  # remove .jpg
        extension = image_name.rsplit('.', 1)[1]

        # Check if image already has a blur level, like '-blur1'
        if 'blur' in base_name:
            name_parts = base_name.split('blur')
            blur_level = int(name_parts[1])
            next_blur_level = max(blur_level - 1, 0)  # decrease blur
            next_image_name = f"{name_parts[0]}blur{next_blur_level}.{extension}"
        else:
            # First wrong attempt, try less blur
            next_image_name = base_name + "blur0." + extension  # maybe no blur image
        
        # You can also check if the file exists before sending it, to avoid 404
        folder_path = data_dir / actual_answer
        next_image_path = folder_path / next_image_name

        if next_image_path.exists():
            return jsonify({
                'correct': False,
                'new_blurred_image_url': f"/data/{actual_answer}/{next_image_name}"
            })
        else:
            # If no better image exists, tell frontend to move to next
            return jsonify({
                'correct': False,
                'new_blurred_image_url': None
            })


@app.route('/random_image', methods=['GET'])
def random_image():
    # Get all subfolders (animal folders)
    animal_folders = [f for f in data_dir.iterdir() if f.is_dir()]

    # Pick a random folder
    random_folder = random.choice(animal_folders)

    # Get all image files in that folder
    image_files = [f for f in random_folder.iterdir() if f.is_file()]

    # Pick a random image
    random_image = random.choice(image_files)
    
    actual_answer = random_image.name.split('-')[0]

    # Return the image file name and its folder path (you can add full URL for easy access)
    return jsonify({
        'image_name': random_image.name,
        'image_actual_answer': actual_answer,
        'image_url': f"/data/{actual_answer}/{random_image.name}"
    })

@app.route('/data/<actual_answer>/<filename>')
def serve_image(actual_answer, filename):
    print(f"actual_answer: {actual_answer}")
    print(f"filename: {filename}")
    folder_path = data_dir / actual_answer
    return send_from_directory(folder_path, filename)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Make sure the images are served under the /static route
    #app.config['UPLOAD_FOLDER'] = 'data'
    app.run(debug=True)
