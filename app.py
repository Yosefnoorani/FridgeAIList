from flask import Flask, request, redirect, url_for, render_template, session
import os
import base64
import json
from detected_fridge_items import generate_list

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1).lower() in {'png', 'jpg', 'jpeg', 'gif'}

def get_missing_items(items, must_have, nice_to_have):
    must_have_items = set(must_have)
    nice_to_have_items = set(nice_to_have)
    missing_items = (must_have_items | nice_to_have_items) - set(items)
    return list(missing_items)

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        data = request.get_json()
        session['family_size'] = data.get('family_size')
        session['budget'] = data.get('budget')
        session['allergies'] = data.get('allergies', [])
        session['must_have'] = data.get('must_have', {})
        session['nice_to_have'] = data.get('nice_to_have', {})

        return redirect(url_for('scan_fridge'))
    return render_template('setup.html')

@app.route('/scan_fridge')
def scan_fridge():
    return render_template('scan_fridge.html',
                           family_size=session.get('family_size', ''),
                           budget=session.get('budget', ''),
                           allergies=session.get('allergies', []),
                           must_have=session.get('must_have', {}),
                           nice_to_have=session.get('nice_to_have', {}))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'images' not in request.form:
        return redirect(request.url)

    must_have = request.form.get('must_have', '').split(',')
    nice_to_have = request.form.get('nice_to_have', '').split(',')

    images_data = request.form['images']
    try:
        images = json.loads(images_data)
        image_paths = []
        for i, image_data in enumerate(images):
            image_data = base64.b64decode(image_data.split(',')[1])
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_image_{i}.png')
            with open(file_path, 'wb') as f:
                f.write(image_data)
            image_paths.append(file_path)

        response = generate_list(image_paths)
        response_data = json.loads(response)

        if not response_data.get("success"):
            return f"Error processing images: {response_data.get('data')}", 400

        items = response_data.get("items", [])
        items = list(set(items))  # Remove duplicates
        missing_items = get_missing_items(items, must_have, nice_to_have)

        return redirect(url_for('results', items=','.join(items), missing_items=','.join(missing_items)))
    except Exception as e:
        return f"Error processing images: {str(e)}", 400

    return redirect(request.url)

@app.route('/results')
def results():
    items = request.args.get('items', '').split(',')
    missing_items = request.args.get('missing_items', '').split(',')
    must_have = session.get('must_have', {})
    nice_to_have = session.get('nice_to_have', {})
    return render_template('results.html', items=items, missing_items=missing_items, must_have=must_have, nice_to_have=nice_to_have)

if __name__ == '__main__':
    app.run(debug=True)
