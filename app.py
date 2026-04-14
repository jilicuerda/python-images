import os
import io
import numpy as np
import tifffile
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def parse_mhd(mhd_path):
    """Lit le fichier MHD pour trouver les dimensions et le fichier RAW associé."""
    header = {}
    with open(mhd_path, 'r') as f:
        for line in f:
            if '=' in line:
                key, val = line.split('=', 1)
                header[key.strip()] = val.strip()
    
    dims = list(map(int, header['DimSize'].split())) # [X, Y, Z]
    dtype = np.uint16 if header['ElementType'] == 'MET_USHORT' else np.uint8
    raw_filename = header['ElementDataFile']
    
    return dims, dtype, raw_filename

def get_slice_data(file_path, z_index):
    """Extrait une matrice 2D (tranche) depuis un TIFF ou un duo MHD/RAW."""
    if file_path.lower().endswith('.mhd'):
        dims, dtype, raw_filename = parse_mhd(file_path)
        raw_path = os.path.join(os.path.dirname(file_path), raw_filename)
        
        # Numpy Memmap : Lit uniquement la tranche requise sans saturer la RAM !
        shape = (dims[2], dims[1], dims[0]) # (Z, Y, X)
        volume = np.memmap(raw_path, dtype=dtype, mode='r', shape=shape)
        return volume[z_index, :, :], dims[2]
        
    else: # Fallback pour les TIFFs multipages
        data = tifffile.imread(file_path, key=z_index)
        with tifffile.TiffFile(file_path) as tif:
            total_slices = len(tif.pages)
        return data, total_slices

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Permet de récupérer plusieurs fichiers (ex: le .mhd ET le .raw)
        files_a = request.files.getlist('files_a')
        files_b = request.files.getlist('files_b')

        if not files_a or not files_b or files_a[0].filename == '':
            return "Veuillez sélectionner les fichiers", 400

        main_filename_a = None
        main_filename_b = None

        # Sauvegarde tous les fichiers de l'Échantillon A (MHD + RAW)
        for f in files_a:
            fname = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            if fname.lower().endswith(('.mhd', '.tif', '.tiff')):
                main_filename_a = fname

        # Sauvegarde tous les fichiers de l'Échantillon B
        for f in files_b:
            fname = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            if fname.lower().endswith(('.mhd', '.tif', '.tiff')):
                main_filename_b = fname

        if not main_filename_a or not main_filename_b:
             return "Fichier principal (MHD ou TIFF) introuvable dans l'upload.", 400

        # Obtenir le nombre total de tranches pour le slider
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], main_filename_a)
        try:
            _, total_slices = get_slice_data(path_a, 0)
        except Exception:
            total_slices = 1 

        return render_template('index.html', 
                               image_a=main_filename_a, 
                               image_b=main_filename_b,
                               total_slices=total_slices)

    return render_template('index.html', image_a=None, image_b=None)

@app.route('/slice/<filename>/<int:z_index>')
def get_slice(filename, z_index):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        data, _ = get_slice_data(file_path, z_index)
        
        # Normalisation visuelle pour le navigateur (16-bit vers 8-bit)
        if data.dtype == np.uint16:
            # On utilise un ratio intelligent pour éviter une image toute noire
            data = (data / np.max(data) * 255).astype(np.uint8) if np.max(data) > 0 else data.astype(np.uint8)
            
        img = Image.fromarray(data)
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
    z_index = data.get('z_index', 0) 
    filename_a = data.get('filename_a')
    filename_b = data.get('filename_b')

    try:
        path_a = os.path.join(app.config['UPLOAD_FOLDER'], filename_a)
        path_b = os.path.join(app.config['UPLOAD_FOLDER'], filename_b)
        
        # 1. Lire les matrices brutes mathématiques
        slice_b, _ = get_slice_data(path_b, 0) 
        slice_a, _ = get_slice_data(path_a, z_index)

        # 2. Créer un canvas vierge 16-bit
        aligned_data = np.zeros_like(slice_b, dtype=slice_b.dtype)

        # 3. Calculer les bordures pour le décalage
        y_start = max(0, offset_y)
        y_end = min(slice_b.shape[0], offset_y + slice_a.shape[0])
        x_start = max(0, offset_x)
        x_end = min(slice_b.shape[1], offset_x + slice_a.shape[1])

        a_y_start = max(0, -offset_y)
        a_y_end = a_y_start + (y_end - y_start)
        a_x_start = max(0, -offset_x)
        a_x_end = a_x_start + (x_end - x_start)

        # 4. Coller les données
        if y_end > y_start and x_end > x_start:
            aligned_data[y_start:y_end, x_start:x_end] = slice_a[a_y_start:a_y_end, a_x_start:a_x_end]

        # 5. Exporter en RAW 16-bit pur
        raw_output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'aligned_slice_{z_index}.raw')
        aligned_data.tofile(raw_output_path)
        
        return jsonify({"status": "success", "message": f"Tranche {z_index} alignée et exportée en RAW 16-bit !"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
