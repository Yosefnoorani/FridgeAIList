import os
from PIL import Image as PILImage
from google.cloud import secretmanager
import google.generativeai as genai
import json
import io
import mimetypes
from dotenv import load_dotenv
import inflect

p = inflect.engine()


def get_secret_cloud(secret_id, project_id="fridgelist-426921", version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def get_secret():
    def is_running_in_cloud():
        return os.getenv('RUNNING_IN_CLOUD') == 'true'

    # secret_key = None
    if is_running_in_cloud():
        # Cloud-specific code
        print("Running in the cloud")
        secret_key = get_secret_cloud("GOOGLE_API_KEY")
    else:
        # Local-specific code
        print("Running locally")
        load_dotenv()
        # secret_key = os.environ.get('GOOGLE_API_KEY')
        secret_key = os.getenv('GOOGLE_API_KEY')
        # print(secret_key)

    return secret_key



def generate_list(image_paths, allergen_list  =["Milk","Egg" ], num_people =2):


    secret_key = get_secret()


    genai.configure(api_key=secret_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    images = []
    for path in image_paths:
        try:
            # Check if file exists
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")

            # Check if the file is an image
            mime_type, _ = mimetypes.guess_type(path)
            if not mime_type or not mime_type.startswith('image'):
                raise ValueError(f"File is not an image: {path}")

            # Open and verify the image
            with open(path, 'rb') as image_file:
                image_bytes = image_file.read()
                PILImage.open(io.BytesIO(image_bytes))
                images.append({
                    'mime_type': mime_type,
                    'data': image_bytes
                })
        except (FileNotFoundError, ValueError, PILImage.UnidentifiedImageError) as e:
            print(f"Error with image {path}: {e}")
            return json.dumps({"success": False, "data": f"Error with image {path}: {e}"})

    string_template  = """
    Please analyze the attached photos of the refrigerator contents. Your task is to identify the products visible in each image and provide a detailed list, including their approximate quantities.

    Requirements:
    
    For each product, provide:
    Name
    Quantity (number only)
    
    Summarize the information across all images to create an accurate inventory of the refrigerator's contents.
    Do not classify items by shelf or drawer.
    Remove duplicate items.
    Return the results in JSON format.
    
    Special Instructions:
    for any items are allergenic from this list: {allergen_list}, mark the allergenic items with ! at the beginning of the word and suggest an alternative item marked with ** at the beginning of the word.
    If you are unable to identify any item, return false for the key named success. If you successfully identified all items, return true for the key named success.
    Remove any unknown food items.
    Combine the duplicate items into one field
    Tailor the list to accommodate the number of people: {num_people}.
    """

    content = string_template.format(allergen_list=allergen_list, num_people=num_people)


    parts = [{'text': content}] + [{'inline_data': image} for image in images]

    try:
        response = model.generate_content({'parts': parts}, stream=True)
        response.resolve()
    except Exception as e:
        print(f"Error generating content: {e}")
        return json.dumps({"success": False, "data": f"Error generating content: {e}"})

    # print(response.text)
    jsonResult = validate_json(response)
    return jsonResult


def validate_json(response):
    if response.candidates[0].finish_reason == 1:
        result = response.text

        # Strip out non-JSON parts
        result = result[result.find('{'):result.rfind('}') + 1]

        try:
            parsed_data = json.loads(result)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)
            return json.dumps({"success": False, "data": "Invalid JSON response"})

        updated_json = json.dumps(parsed_data)
        print(updated_json)
        return updated_json
    else:
        updated_data = {
            "success": False,
            "data": str(response.candidates[0].safety_ratings)
        }
        updated_json = json.dumps(updated_data)
        # print(updated_json)
        return updated_json


def singularize(name):
    return p.singular_noun(name) if p.singular_noun(name) else name


def get_missing_items(scanned_items, must_have, nice_to_have):
    missing_items = {}
    nice_to_have_changes = {}
    scanned_items_dict = {singularize(item['name'].lower()): item['quantity'] for item in scanned_items}

    for item, quantity in must_have.items():
        sanitized_quantity = sanitize_quantity(quantity)
        item_singular = singularize(item.lower())
        scanned_quantity = scanned_items_dict.get(item_singular, 0)
        remaining_quantity = sanitized_quantity - scanned_quantity
        if remaining_quantity > 0:
            missing_items[item_singular] = remaining_quantity

    for item, quantity in nice_to_have.items():
        sanitized_quantity = sanitize_quantity(quantity)
        item_singular = singularize(item.lower())
        scanned_quantity = scanned_items_dict.get(item_singular, 0)
        if sanitized_quantity > scanned_quantity:
            nice_to_have_changes[item_singular] = sanitized_quantity - scanned_quantity

    return missing_items, nice_to_have_changes


def sanitize_quantity(quantity):
    try:
        sanitized_quantity = int(''.join(filter(str.isdigit, str(quantity))))
        return sanitized_quantity
    except ValueError:
        return 0


def sanitize_items(items):
    return {item: sanitize_quantity(quantity) for item, quantity in items.items()}


if __name__ == '__main__':

    # prt = generate_list(image_paths=r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_-49.jpg")

    # prt = generate_list(image_paths=r"C:\Users\yosef\Downloads\fridgeCompie2.jpg")


    prt = generate_list(image_paths=[r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-49.jpg",
                                r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-44.jpg",
                                r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-39.jpg",
                                r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-34.jpg",
                                r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-28.jpg",
                                r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-23.jpg",
                                r"C:\Users\yosef\Downloads\fridges images\photo_2024-06-21_00-03-15.jpg"])


    print(prt)



# def check_image(image_data):
#     try:
#         # Try to open the image to see if it is valid
#         image = Image.open(io.BytesIO(image_data))
#         image.verify()
#         return True
#     except Exception as e:
#         print(f"Invalid image: {e}")
#         return False

#
#
# @app.route('/generate', methods=['POST'])
# def generate_from_image():
#     if 'image' not in request.files:
#         return jsonify({'error': 'No image provided'})
#
#     print("Start request")
#     image = request.files['file']
#     # print(image)
#     if image.filename == '':
#         return jsonify({'error': 'No selected image file'})
#
#     # Save the image to a temporary location
#     temp_image_path = 'temp_image.jpg'
#     image.save(temp_image_path)
#
#     # Generate content from the image
#     generated_text = generate_content(temp_image_path)
#     # generated_text = generate_content(image)
#     # print(generated_text)
#     os.remove(temp_image_path)
#
#
#
#     print("End response")
#     # print(generated_text)
#     return generated_text




#     google_api_key = "AIzaSyDra4rh0oD4P3PcpiRYEyFy6dl1mywTaEI"