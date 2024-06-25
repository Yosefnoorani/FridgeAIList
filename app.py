import json
from flask import Flask, request, redirect, url_for, render_template
import os
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def generate(file_path):
    # This function should implement the actual image processing and recognition logic
    return ['milk', 'eggs', 'butter']  # Placeholder for demo purposes

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
        family_size = data.get('family_size')
        budget = data.get('budget')
        allergies = data.get('allergies', [])
        must_have = data.get('must_have', {})
        nice_to_have = data.get('nice_to_have', {})

        print('Family Size:', family_size)
        print('Budget:', budget)
        print('Allergies:', allergies)
        print('Must Have:', must_have)
        print('Nice to Have:', nice_to_have)

        return redirect(url_for('scan_fridge',
                                family_size=family_size,
                                budget=budget,
                                allergies=json.dumps(allergies),
                                must_have=json.dumps(must_have),
                                nice_to_have=json.dumps(nice_to_have)))
    return render_template('setup.html')


@app.route('/scan_fridge')
def scan_fridge():
    family_size = request.args.get('family_size', '')
    budget = request.args.get('budget', '')
    allergies = json.loads(request.args.get('allergies', '[]'))
    must_have = json.loads(request.args.get('must_have', '{}'))
    nice_to_have = json.loads(request.args.get('nice_to_have', '{}'))

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

    must_have = request.form.get('must_have', '').split(',')
    nice_to_have = request.form.get('nice_to_have', '').split(',')

    images_data = request.form['images']
    try:
        images = json.loads(images_data)
        items = []
        for i, image_data in enumerate(images):
            image_data = base64.b64decode(image_data.split(',')[1])
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_image_{i}.png')
            with open(file_path, 'wb') as f:
                f.write(image_data)
            items.extend(generate(file_path))
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
    return render_template('results.html', items=items, missing_items=missing_items)

if __name__ == '__main__':
    app.run(debug=True)
