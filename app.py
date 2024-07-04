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

def get_missing_items(scanned_items, must_have):
    missing_items = {}
    for item, quantity in must_have.items():
        scanned_item = next((si for si in scanned_items if si['name'].lower() == item.lower()), None)
        if scanned_item:

            remaining_quantity = int(quantity) - scanned_item['quantity']
            if remaining_quantity > 0:
                missing_items[item] = remaining_quantity
        else:
            missing_items[item] = (quantity)
    return missing_items

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
    family_size = session.get('family_size', '')
    budget = session.get('budget', '')
    allergies = session.get('allergies', [])
    must_have = session.get('must_have', {})
    nice_to_have = session.get('nice_to_have', {})

    # Ensure must_have and nice_to_have are dictionaries
    if must_have is None:
        must_have = {}
    if nice_to_have is None:
        nice_to_have = {}

    return render_template('scan_fridge.html',
                           family_size=family_size,
                           budget=budget,
                           allergies=allergies,
                           must_have=must_have,
                           nice_to_have=nice_to_have)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'images' not in request.form:
        return redirect(request.url)

    must_have = request.form.get('must_have', '{}')
    nice_to_have = request.form.get('nice_to_have', '{}')

    try:
        must_have = json.loads(must_have)
        nice_to_have = json.loads(nice_to_have)
    except json.JSONDecodeError as e:
        return render_template('scan_fridge.html', error_message=f'Error decoding JSON: {str(e)}')

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
        print(response_data)

        if not response_data.get("success"):
            error_message = response_data.get('data') or 'Unknown error occurred during image processing.'
            return render_template('scan_fridge.html', error_message=error_message)

        items = response_data.get("items", [])

        # Debugging print statements
        print("Items from scan:", items)
        print("Must have items:", must_have)

        missing_items = get_missing_items(items, must_have)

        return redirect(url_for('results', items=json.dumps(items), missing_items=json.dumps(missing_items)))
    except json.JSONDecodeError as e:
        return render_template('scan_fridge.html', error_message='Invalid image data format.')
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return render_template('scan_fridge.html', error_message=str(e))

    return redirect(request.url)


@app.route('/results')
def results():
    items = json.loads(request.args.get('items', '[]'))
    missing_items = json.loads(request.args.get('missing_items', '{}'))
    must_have = session.get('must_have', {})
    nice_to_have = session.get('nice_to_have', {})
    return render_template('results.html', items=items, missing_items=missing_items, must_have=must_have, nice_to_have=nice_to_have)


if __name__ == '__main__':
    app.run(debug=True)
