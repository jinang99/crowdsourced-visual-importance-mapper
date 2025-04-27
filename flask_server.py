import random
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, render_template
from flask_cors import CORS

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Set your base folder path
data_dir = Path('data')

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
