from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
import os
from werkzeug.utils import secure_filename
import logging
import json
import re
from datetime import datetime
try:
    import boto3
    from botocore.exceptions import NoCredentialsError
except ImportError as e:
    if 'boto3' in str(e):
        print("boto3 is not installed. Please install it using: pip install boto3")
    elif 'botocore' in str(e):
        print("botocore is not installed. Please install it using: pip install botocore")
    import sys
    sys.exit(1)
from decouple import config
import requests # type: ignore
import sys

# Set up logging to console for better debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'}

# Load configuration with better error handling
try:
    # AWS S3 Configuration
    USE_S3 = config('USE_S3', default=False, cast=bool)
    
    # AI Service Configuration
    USE_AI_SERVICE = config('USE_AI_SERVICE', default=True, cast=bool)
    AI_API_KEY = config('AI_API_KEY', default="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")
    AI_API_URL = config('AI_API_URL', default="https://api.openai.com/v1/chat/completions")
    
    logger.info(f"Configuration loaded: USE_S3={USE_S3}, USE_AI_SERVICE={USE_AI_SERVICE}")
    
    if USE_S3:
        AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
        AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
        AWS_REGION = config('AWS_REGION', default='us-east-1')
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    # Set defaults if configuration fails
    USE_S3 = False
    USE_AI_SERVICE = False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_s3(file_path, bucket, s3_file_name):
    """
    Upload a file to an S3 bucket
    """
    try:
        s3_client.upload_file(file_path, bucket, s3_file_name)
        return True
    except NoCredentialsError:
        app.logger.error("AWS credentials not available")
        return False
    except Exception as e:
        app.logger.error(f"Error uploading to S3: {e}")
        return False

def get_s3_url(bucket, s3_file_name):
    """
    Generate a URL for the file in S3
    """
    return f"https://{bucket}.s3.amazonaws.com/{s3_file_name}"

@app.route('/')
def index():
    files = []
    try:
        if USE_S3:
            # List files from S3
            response = s3_client.list_objects_v2(Bucket=AWS_STORAGE_BUCKET_NAME)
            if 'Contents' in response:
                for item in response['Contents']:
                    files.append({
                        'name': item['Key'],
                        'path': get_s3_url(AWS_STORAGE_BUCKET_NAME, item['Key']),
                        's3': True
                    })
        else:
            # List files from local storage
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                files.append({
                    'name': filename,
                    'path': os.path.join(app.config['UPLOAD_FOLDER'], filename),
                    's3': False
                })
        logger.info(f"Found {len(files)} files to display")
    except Exception as e:
        logger.error(f"Error listing files: {e}")
    
    # Check if templates directory exists
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(template_path):
        logger.error(f"Templates directory not found at {template_path}")
        return "Error: Templates directory not found. Please create a 'templates' folder with index.html"
    
    # Check if index.html exists
    index_path = os.path.join(template_path, 'index.html')
    if not os.path.exists(index_path):
        logger.error(f"index.html not found at {index_path}")
        return "Error: index.html not found. Please create an index.html file in the templates folder."
    
    return render_template('index.html', files=files, use_s3=USE_S3)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            app.logger.warning('No file part in request')
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            app.logger.warning('No selected file')
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save file locally first
            file.save(file_path)
            
            # If S3 is enabled, upload to S3
            s3_url = None
            if USE_S3:
                if upload_to_s3(file_path, AWS_STORAGE_BUCKET_NAME, filename):
                    s3_url = get_s3_url(AWS_STORAGE_BUCKET_NAME, filename)
                    # Optionally remove local file after S3 upload
                    os.remove(file_path)
                else:
                    return jsonify({'error': 'Failed to upload to S3'}), 500
            
            app.logger.info(f'File uploaded successfully: {filename}')
            return jsonify({
                'message': 'File uploaded successfully',
                'filename': filename,
                's3_url': s3_url
            })
        
        app.logger.warning(f'Invalid file type: {file.filename}')
        return jsonify({'error': 'File type not allowed'}), 400

    except Exception as e:
        app.logger.error(f'Error during file upload: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if USE_S3:
        # Redirect to S3 URL
        return redirect(get_s3_url(AWS_STORAGE_BUCKET_NAME, filename))
    else:
        # Serve from local storage
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        
        # Process the message and generate a response
        response = process_chat_message(message)
        
        return jsonify({
            'response': response
        })
    except Exception as e:
        app.logger.error(f'Error processing chat message: {e}')
        return jsonify({
            'response': 'Sorry, I encountered an error processing your request.'
        }), 500

def process_chat_message(message):
    """
    Process the user's chat message and generate a response.
    This can use an AI service if enabled, or fall back to rule-based responses.
    """
    # Get list of files for reference
    files = []
    try:
        if USE_S3:
            # List files from S3
            response = s3_client.list_objects_v2(Bucket=AWS_STORAGE_BUCKET_NAME)
            if 'Contents' in response:
                files = [item['Key'] for item in response['Contents']]
        else:
            # List files from local storage
            files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f))]
    except Exception as e:
        app.logger.error(f"Error listing files: {e}")
    
    # Try to use AI service if enabled
    if USE_AI_SERVICE:
        try:
            # Prepare context about files
            file_context = "Available files: " + ", ".join(files) if files else "No files uploaded yet."
            
            # Call AI service API
            headers = {
                "Authorization": f"Bearer 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",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",  # Adjust model as needed
                "messages": [
                    {"role": "system", "content": f"You are a helpful assistant for a file management application. {file_context}"},
                    {"role": "user", "content": message}
                ],
                "max_tokens": 500
            }
            
            response = requests.post(AI_API_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                ai_response = response.json()
                return ai_response["choices"][0]["message"]["content"]
            else:
                app.logger.error(f"AI service error: {response.status_code} - {response.text}")
                # Fall back to rule-based responses
        except Exception as e:
            app.logger.error(f"Error using AI service: {e}")
            # Fall back to rule-based responses
    
    # Convert message to lowercase for easier matching
    message_lower = message.lower()
    
    # Check if the message is asking about files
    if any(keyword in message_lower for keyword in ['list', 'show', 'what', 'files', 'documents', 'uploaded']):
        if not files:
            return "You haven't uploaded any files yet. You can upload files in the Upload tab."
        
        file_types = {
            'images': [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))],
            'pdfs': [f for f in files if f.lower().endswith('.pdf')],
            'videos': [f for f in files if f.lower().endswith(('.mp4', '.mov'))]
        }
        
        response = "Here are the files you've uploaded:\n\n"
        
        if file_types['images']:
            response += f"Images ({len(file_types['images'])}): {', '.join(file_types['images'])}\n\n"
        
        if file_types['pdfs']:
            response += f"PDFs ({len(file_types['pdfs'])}): {', '.join(file_types['pdfs'])}\n\n"
        
        if file_types['videos']:
            response += f"Videos ({len(file_types['videos'])}): {', '.join(file_types['videos'])}\n\n"
        
        response += "You can view or download these files in the Gallery tab."
        return response
    
    # Check if the message is asking about a specific file
    for file in files:
        if file.lower() in message_lower:
            if USE_S3:
                # Get file metadata from S3
                try:
                    response = s3_client.head_object(Bucket=AWS_STORAGE_BUCKET_NAME, Key=file)
                    file_size = response['ContentLength']
                    file_modified = response['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    app.logger.error(f"Error getting S3 file metadata: {e}")
                    continue
            else:
                # Get file metadata from local storage
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
                file_stats = os.stat(file_path)
                file_size = file_stats.st_size
                file_modified = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            # Determine file type
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                file_type = "Image"
            elif file.lower().endswith('.pdf'):
                file_type = "PDF document"
            elif file.lower().endswith(('.mp4', '.mov')):
                file_type = "Video"
            else:
                file_type = "File"
            
            # Format file size
            if file_size < 1024:
                size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"
            
            return f"I found information about '{file}':\n\n" \
                   f"Type: {file_type}\n" \
                   f"Size: {size_str}\n" \
                   f"Last modified: {file_modified}\n\n" \
                   f"You can view or download this file in the Gallery tab."
    
    # General responses based on keywords
    if any(keyword in message_lower for keyword in ['hello', 'hi', 'hey', 'greetings']):
        return "Hello! I'm your AI assistant. I can help you analyze and discuss your uploaded files. What would you like to know?"
    
    if any(keyword in message_lower for keyword in ['thank', 'thanks']):
        return "You're welcome! Is there anything else I can help you with?"
    
    if any(keyword in message_lower for keyword in ['help', 'how', 'can you']):
        return "I can help you with your uploaded files in several ways:\n\n" \
               "1. List all your uploaded files\n" \
               "2. Provide information about specific files\n" \
               "3. Answer questions about file types and formats\n" \
               "4. Guide you on how to upload, view, and download files\n\n" \
               "Just let me know what you need!"
    
    # Default response
    return "I'm here to help you with your uploaded files. You can ask me to list your files, provide information about specific files, or help you navigate the application. What would you like to know?"

if __name__ == '__main__':
    # Use environment variable for port with a default of 8888
    port = int(os.environ.get('PORT', 8888))
    
    # Check if templates directory exists before starting
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(template_path):
        logger.error(f"Templates directory not found at {template_path}")
        print(f"ERROR: Templates directory not found at {template_path}")
        print("Please create a 'templates' folder with index.html before running the app")
        sys.exit(1)
    
    # Log startup information
    logger.info(f"Starting Flask application on port {port}")
    print(f"Starting Flask application on port {port}")
    print(f"Open your browser and navigate to http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=True)  # Enable debug mode for troubleshooting
