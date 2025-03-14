# File Management Application

A simple web application for managing files with AI-powered chat assistance.

## Features

- Upload and manage files (images, PDFs, videos)
- View files in a gallery
- Chat with an AI assistant about your files
- Optional S3 storage integration

## Setup Instructions

### 1. Install Dependencies

```bash
pip install flask boto3 python-decouple requests
```

### 2. Configuration

Create a `.env` file in the project root with the following variables:

```
# AI Service Configuration
USE_AI_SERVICE=True
AI_API_KEY=your_api_key_here
AI_API_URL=https://api.openai.com/v1/chat/completions

# Optional S3 Configuration
USE_S3=False
# If USE_S3 is True, add these:
# AWS_ACCESS_KEY_ID=your_aws_access_key
# AWS_SECRET_ACCESS_KEY=your_aws_secret_key
# AWS_STORAGE_BUCKET_NAME=your_bucket_name
# AWS_REGION=us-east-1
```

### 3. Create Required Directories

The application needs these directories:
- `templates/` - Contains HTML templates
- `static/` - Contains static files like images
- `uploads/` - Where uploaded files are stored

### 4. Run the Application

```bash
python app.py
```

The application will start on port 8888 by default. Open your browser and navigate to:
```
http://localhost:8888
```

## Troubleshooting

If you encounter issues:

1. Check the console output for error messages
2. Verify that all required directories exist
3. Make sure your `.env` file is properly configured
4. Check that you have the necessary permissions for file operations

## File Structure

```
project/
├── app.py              # Main application file
├── .env                # Environment variables (create this)
├── README.md           # This file
├── templates/          # HTML templates
│   └── index.html      # Main template
├── static/             # Static files
│   ├── file-icon.png   # Generic file icon
│   ├── pdf-icon.png    # PDF file icon
│   └── video-icon.png  # Video file icon
└── uploads/            # Directory for uploaded files
```
