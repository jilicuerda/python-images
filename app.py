import os
import io
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file_a = request.files.get('file_a')
        file_b = request.files.get('file_b')

        if not file_a or not file_b or file_a.filename == '' or file_b.filename == '':
            return "Please select both files", 400

        filename_a = secure_filename(file_a.filename)
        filename_b = secure_filename(file_b.filename)
        
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], filename_a)
        path_b = os.path.join(app.config['UPLOAD_FOLDER'], filename_b)
        
        file_a.save(path_a)
        file_b.save(path_b)

        # Get the total number of slices (depth) of the 3D images
        # We assume Image A is the 3D stack we want to slice through
        try:
            img_3d = Image.open(path_a)
            total_slices = getattr(img_3d, "n_frames", 1) 
        except Exception:
            total_slices = 1 # Fallback if it's just a 2D image

        return render_template('index.html', 
                               image_a=filename_a, 
                               image_b=filename_b,
                               total_slices=total_slices)

    return render_template('index.html', image_a=None, image_b=None)

# --- NEW: Dynamic 3D Slicing Endpoint ---
@app.route('/slice/<filename>/<int:z_index>')
def get_slice(filename, z_index):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        img = Image.open(file_path)
        # Go to the requested Z-slice in the 3D stack
        if hasattr(img, 'n_frames') and z_index < img.n_frames:
            img.seek(z_index)
        
        # Convert the specific slice to PNG in memory so the browser can read it
        img_io = io.BytesIO()
        img.convert("RGBA").save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        return str(e), 500

@app.route('/align', methods=['POST'])
def align_images():
    data = request.json
    offset_x = data.get('x', 0)
    offset_y = data.get('y', 0)
    z_index = data.get('z_index', 0) # Get the specific slice they aligned
    filename_a = data.get('filename_a')
    filename_b = data.get('filename_b')

    try:
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], filename_a)
        path_b = os.path.join(app.config['UPLOAD_FOLDER'], filename_b)
        
        # Open Base
        img_b = Image.open(path_b)
        if hasattr(img_b, 'n_frames'):
            img_b.seek(0) # Assuming we align to the first slice of the base, adjust as needed

        # Open Overlay and seek to the exact slice the user was looking at
        img_a = Image.open(path_a)
        if hasattr(img_a, 'n_frames'):
            img_a.seek(z_index)

        aligned_canvas = Image.new("RGBA", img_b.size)
        aligned_canvas.paste(img_b.convert("RGBA"), (0, 0))
        aligned_canvas.paste(img_a.convert("RGBA"), (offset_x, offset_y))
        
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'aligned_result_slice_{z_index}.png')
        aligned_canvas.save(output_path)
        
        return jsonify({"status": "success", "message": f"Slice {z_index} aligned and saved!"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
