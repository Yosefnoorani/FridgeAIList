from flask import Flask, request, redirect, url_for, render_template, session, jsonify
import os
import base64
import json
from detected_fridge_items import generate_list
from detected_fridge_items import get_missing_items, sanitize_items
from google.cloud import storage



app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# Initialize Google Cloud Storage client
storage_client = storage.Client()
bucket_name = 'fridgelist_actionlogs'
log_blob_name = 'logs.json'

def get_log_blob():
    bucket = storage_client.get_bucket(bucket_name)
    return bucket.blob(log_blob_name)


@app.route('/log', methods=['POST'])
def log_data():
    log_entry = request.json
    if not log_entry:
        return jsonify({'status': 'fail', 'message': 'No data provided'}), 400

    try:
        log_blob = get_log_blob()

        # Download existing logs
        if log_blob.exists():
            logs = json.loads(log_blob.download_as_text())
        else:
            logs = []

        # Append new log entry
        logs.append(log_entry)

        # Upload logs back to Cloud Storage
        log_blob.upload_from_string(json.dumps(logs, indent=2))

        return jsonify({'status': 'success', 'message': 'Log saved'}), 200

    except Exception as e:
        print(f"Error logging data: {e}")
        return jsonify({'status': 'fail', 'message': 'Internal server error'}), 500



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1).lower() in {'png', 'jpg', 'jpeg', 'gif'}



@app.route('/')
def index():
    return render_template('home.html')

from detected_fridge_items import allergies_insight

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        data = request.get_json()
        family_size = data.get('family_size')
        budget = data.get('budget')
        allergies = data.get('allergies', [])
        must_have = data.get('must_have', {})
        nice_to_have = data.get('nice_to_have', {})

        must_nice_allergy_list = allergies_insight(must_have, nice_to_have, allergies)
        print(must_nice_allergy_list)

        session['family_size'] = family_size
        session['budget'] = budget
        session['allergies'] = allergies
        session['must_nice_allergy_list'] = must_nice_allergy_list
        return redirect(url_for('scan_fridge'))
    return render_template('setup.html')


@app.route('/scan_fridge')
def scan_fridge():
    family_size = session.get('family_size', '')
    budget = session.get('budget', '')
    allergies = session.get('allergies', [])
    # must_have = session.get('must_have', {})
    # nice_to_have = session.get('nice_to_have', {})
    must_nice_allergy_list = session.get('must_nice_allergy_list', {})
    # print("must_nice_allergy_list: ",must_nice_allergy_list)

    # Ensure must_have and nice_to_have are dictionaries
    if must_nice_allergy_list is None:
        must_nice_allergy_list = {}
    # if nice_to_have is None:
    #     nice_to_have = {}

    error_message = request.args.get('error_message', '')

    return render_template('scan_fridge.html',
                           family_size=family_size,
                           budget=budget,
                           allergies=allergies,
                           must_nice_allergy_list = must_nice_allergy_list,
                           # must_have=must_have,
                           # nice_to_have=nice_to_have,
                           error_message=error_message)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'images' not in request.form:
        return redirect(request.url)

    must_nice_allergy_list = request.form.get('must_nice_allergy_list', '{}')

    try:
        must_nice_allergy_list = json.loads(must_nice_allergy_list)
        # print(f"must_nice_allergy_list (after JSON load): {must_nice_allergy_list} - type: {type(must_nice_allergy_list)}")
    except json.JSONDecodeError as e:
        # print(f"Error decoding must_nice_allergy_list JSON: {e}")
        return render_template('scan_fridge.html', error_message=f'Error decoding JSON: {str(e)}')

    images_data = request.form['images']
    try:
        images = json.loads(images_data)
        # print(f"images (after JSON load): {images} - type: {type(images)}")
        image_paths = []
        for i, image_data in enumerate(images):
            image_data = base64.b64decode(image_data.split(',')[1])
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_image_{i}.png')
            with open(file_path, 'wb') as f:
                f.write(image_data)
            image_paths.append(file_path)

        # Retrieve allergen_list and num_people from session
        allergen_list = session.get('allergies', [])
        num_people = session.get('family_size', 1)
        # print(f"allergen_list: {allergen_list}, num_people: {num_people}")

        # Pass image_paths, allergen_list, and num_people to generate_list
        response = generate_list(image_paths, allergen_list, num_people)
        response_data = json.loads(response)
        # print(f"response_data: {response_data} - type: {type(response_data)}")

        if not response_data.get("success"):
            error_message = response_data.get('data') or 'Unknown error occurred during image processing.'
            return render_template('scan_fridge.html', error_message=error_message, must_nice_allergy_list=must_nice_allergy_list)

        items = response_data.get("items", [])
        # print(f"items: {items} - type: {type(items)}")

        missing_items = get_missing_items(items, must_nice_allergy_list)
        # print(f"missing_items: {missing_items} - type: {type(missing_items)}")

        return redirect(url_for('results', items=json.dumps(items), missing_items=json.dumps(missing_items), must_nice_allergy_list=json.dumps(must_nice_allergy_list)))
    except json.JSONDecodeError as e:
        print(f"Error decoding images JSON: {e}")
        return render_template('scan_fridge.html', error_message='Invalid image data format.', must_nice_allergy_list=must_nice_allergy_list)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return render_template('scan_fridge.html', error_message=str(e), must_nice_allergy_list=must_nice_allergy_list)

    return redirect(request.url)


@app.route('/results')
def results():
    items_str = request.args.get('items', '[]')
    missing_items_str = request.args.get('missing_items', '{}')
    must_nice_allergy_list_str = request.args.get('must_nice_allergy_list', '{}')

    try:
        items = json.loads(items_str)
        missing_items = json.loads(missing_items_str)
        must_nice_allergy_list = json.loads(must_nice_allergy_list_str)
        # print(f"items: {items}")
        # print(f"missing_items: {missing_items}")
        # print(f"must_nice_allergy_list: {must_nice_allergy_list}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        items = []
        missing_items = {}
        must_nice_allergy_list = {}

    return render_template('results.html', items=items, missing_items=missing_items, must_nice_allergy_list=must_nice_allergy_list)


if __name__ == '__main__':
    app.run(debug=True)
