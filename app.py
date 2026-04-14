import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)

# We will save uploads inside static/uploads so the frontend can easily read them
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists when the app starts
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Check if the post request has both file parts
        if 'file_a' not in request.files or 'file_b' not in request.files:
            return "Missing files in request", 400
        
        file_a = request.files['file_a']
        file_b = request.files['file_b']

        if file_a.filename == '' or file_b.filename == '':
            return "Please select both files", 400

        # Secure the filenames and save them to the server
        filename_a = secure_filename(file_a.filename)
        filename_b = secure_filename(file_b.filename)
        
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], filename_a)
        path_b = os.path.join(app.config['UPLOAD_FOLDER'], filename_b)
        
        file_a.save(path_a)
        file_b.save(path_b)

        # Re-render the page, but this time pass the saved filenames to activate the canvas
        return render_template('index.html', image_a=filename_a, image_b=filename_b)

    # If it's a GET request (first time visiting the page), just show the upload form
    return render_template('index.html', image_a=None, image_b=None)

@app.route('/align', methods=['POST'])
def align_images():
    data = request.json
    offset_x = data.get('x', 0)
    offset_y = data.get('y', 0)
    
    # We need to know which files we are aligning
    filename_a = data.get('filename_a')
    filename_b = data.get('filename_b')

    try:
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], filename_a)
        path_b = os.path.join(app.config['UPLOAD_FOLDER'], filename_b)
        
        img_a = Image.open(path_a)
        img_b = Image.open(path_b)

        aligned_canvas = Image.new("RGBA", img_b.size)
        
        aligned_canvas.paste(img_b, (0, 0))
        aligned_canvas.paste(img_a, (offset_x, offset_y))
        
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'aligned_result.png')
        aligned_canvas.save(output_path)
        
        return jsonify({"status": "success", "message": "Images aligned and saved successfully!"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
