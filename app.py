from flask import Flask, request, redirect, url_for, render_template, session
import os
import base64
import json
from detected_fridge_items import generate_list
from detected_fridge_items import get_missing_items, sanitize_items



app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1).lower() in {'png', 'jpg', 'jpeg', 'gif'}

# def singularize(name):
#     return p.singular_noun(name) if p.singular_noun(name) else name
#
# def get_missing_items(scanned_items, must_have):
#     missing_items = {}
#     scanned_items_dict = {singularize(item['name'].lower()): item['quantity'] for item in scanned_items}
#     for item, quantity in must_have.items():
#         sanitized_quantity = sanitize_quantity(quantity)
#         item_singular = singularize(item.lower())
#         scanned_quantity = scanned_items_dict.get(item_singular, 0)
#         remaining_quantity = sanitized_quantity - scanned_quantity
#         if remaining_quantity > 0:
#             missing_items[item_singular] = remaining_quantity
#     return missing_items
#
# def sanitize_quantity(quantity):
#     try:
#         sanitized_quantity = int(''.join(filter(str.isdigit, str(quantity))))
#         return sanitized_quantity
#     except ValueError:
#         return 0
#
# def sanitize_items(items):
#     return {item: sanitize_quantity(quantity) for item, quantity in items.items()}

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

    must_have = sanitize_items(must_have)
    nice_to_have = sanitize_items(nice_to_have)

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
            return render_template('scan_fridge.html', error_message=error_message, must_have=must_have, nice_to_have=nice_to_have)

        items = response_data.get("items", [])

        # Debugging print statements
        print("Items from scan:", items)
        print("Must have items:", must_have)
        print("Nice to have items:", nice_to_have)

        missing_items, nice_to_have_changes = get_missing_items(items, must_have, nice_to_have)

        return redirect(url_for('results', items=json.dumps(items), missing_items=json.dumps(missing_items), nice_to_have=json.dumps(nice_to_have_changes)))
    except json.JSONDecodeError as e:
        return render_template('scan_fridge.html', error_message='Invalid image data format.', must_have=must_have, nice_to_have=nice_to_have)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return render_template('scan_fridge.html', error_message=str(e), must_have=must_have, nice_to_have=nice_to_have)

    return redirect(request.url)


@app.route('/results')
def results():
    items = json.loads(request.args.get('items', '[]'))
    missing_items = json.loads(request.args.get('missing_items', '{}'))
    nice_to_have_changes = json.loads(request.args.get('nice_to_have', '{}'))
    must_have = session.get('must_have', {})
    allergies = session.get('allergies', [])

    # Process allergy items
    allergy_items = []
    for item in items:
        if item['name'] in allergies:
            allergy_items.append({
                'name': item['name'],
                'alternative': item.get('alternative', 'None'),
                'quantity': item['quantity']
            })

    return render_template('results.html', items=items, missing_items=missing_items, must_have=must_have,
                           nice_to_have=nice_to_have_changes, allergy_items=allergy_items)

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

    error_message = request.args.get('error_message', '')

    return render_template('scan_fridge.html',
                           family_size=family_size,
                           budget=budget,
                           allergies=allergies,
                           must_have=must_have,
                           nice_to_have=nice_to_have,
                           error_message=error_message)



if __name__ == '__main__':
    app.run(debug=True)
