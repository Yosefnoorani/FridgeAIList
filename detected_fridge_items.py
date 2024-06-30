import os
from PIL import Image as PILImage
from google.cloud import secretmanager
import google.generativeai as genai
import json
import io
import mimetypes
from dotenv import load_dotenv



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
        print(secret_key)

    return secret_key



def generate_list(image_paths):


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

    content = """
    Please analyze the attached photos of the contents of the refrigerator. 
    Identify the products visible in each image and provide a list of those products along 
    with their approximate quantities. For each product, state the name, quantity, and if possible, 
    the current state (e.g., full, half full, almost empty). Summarize the information across all images 
    to ensure an accurate inventory of the refrigerator's contents. Do not classify by shelf or drawer. 
    Return the results in JSON format: 
    {"success": true, "items": [{"name": "the Item Name 1", "quantity": number, "state": "full or half"}, 
    {"name": "the Item Name 2", "quantity": number, "state": "full or half"}]}
    If you were unable to identify it, return the value false to the key named success; if you were able 
    to identify it, return a value true.
    """

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