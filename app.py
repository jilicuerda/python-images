import os
from flask import Flask, render_template, request, jsonify
from PIL import Image

app = Flask(__name__)

# In a real app, you'd handle file uploads. 
# For this example, we assume the images are already in a 'static' folder.
UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    # Pass the image filenames to the frontend
    # You will need two dummy images in a folder named 'static' to test this locally
    return render_template('index.html', image_a='image_a.png', image_b='image_b.png')

@app.route('/align', methods=['POST'])
def align_images():
    data = request.json
    offset_x = data.get('x', 0)
    offset_y = data.get('y', 0)
    
    print(f"Received alignment data: Move Image A by X: {offset_x}px, Y: {offset_y}px")

    try:
        # Load the images
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], 'image_a.png')
        path_b = os.path.join(app.config['UPLOAD_FOLDER'], 'image_b.png')
        
        img_a = Image.open(path_a)
        img_b = Image.open(path_b)

        # Create a new blank canvas the size of Image B
        # In a real scenario, you might want to expand the canvas depending on the shift
        aligned_canvas = Image.new("RGBA", img_b.size)
        
        # Paste Image B (the base)
        aligned_canvas.paste(img_b, (0, 0))
        
        # Paste Image A (the moving image) at the new offset coordinates
        # We use it as its own mask to preserve transparency if it has any
        aligned_canvas.paste(img_a, (offset_x, offset_y))
        
        # Save the result
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'aligned_result.png')
        aligned_canvas.save(output_path)
        
        return jsonify({"status": "success", "message": "Images aligned and saved!"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Render requires apps to bind to 0.0.0.0
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
