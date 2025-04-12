import os
import sys
import io
import json
from django.http import JsonResponse
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.urls import path
from django.core.management import execute_from_command_line
from django.views.decorators.csrf import csrf_exempt

# Import PDFMiner components
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

# Basic settings
settings.configure(
    DEBUG=True,  # Set to True for development
    ROOT_URLCONF=__name__,
    SECRET_KEY='1_d0nt_kn0w_what_t0_keep',
    ALLOWED_HOSTS=['*'],
    MIDDLEWARE=[
        'django.middleware.common.CommonMiddleware',
        'django.middleware.security.SecurityMiddleware',
    ],
)

# Implement a simple authentication check
API_KEY = os.environ.get('API_KEY', 'default_key_for_development')

def check_auth(request):
    """Check if the request has a valid API key"""
    auth_header = request.headers.get('Authorization', '')
    
    # Skip auth check if no API_KEY is set (for development/testing)
    if API_KEY == 'default_key_for_development':
        return True
        
    # Check for bearer token
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        return token == API_KEY
    
    return False

# Function to process PDF and extract text using PDFMiner
def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using PDFMiner"""
    output_string = io.StringIO()
    try:
        # Create a temporary file to store the uploaded PDF content
        temp_path = "/tmp/temp_pdf.pdf"
        with open(temp_path, 'wb') as f:
            for chunk in pdf_file.chunks():
                f.write(chunk)
        
        with open(temp_path, 'rb') as in_file:
            parser = PDFParser(in_file)
            doc = PDFDocument(parser)
            rsrcmgr = PDFResourceManager()
            device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            
            for page in PDFPage.create_pages(doc):
                interpreter.process_page(page)
        
        # Clean up
        os.remove(temp_path)
        
    except Exception as e:
        return f"Error extracting text: {str(e)}"
    
    return output_string.getvalue()

# Function to classify document type
def classify_document(text):
    categories = {
        "permissionLetter": ["permission letter", "signed letter", "approval"],
        "offerLetter": ["offer letter", "employment offer", "job offer"],
        "completionCertificate": ["completion certificate", "certification", "internship completed"],
        "internshipReport": ["internship report", "work summary", "project report"],
        "studentFeedback": ["student feedback", "internship experience", "review"],
        "employerFeedback": ["employer feedback", "performance review", "student evaluation"]
    }
    
    for category, keywords in categories.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return category
    return "unknown"

# View function with JSON response
@csrf_exempt
def upload_pdf(request):
    # Debug info
    print("Request method:", request.method)
    print("Request headers:", request.headers)
    print("Files in request:", request.FILES)
    print("File keys:", list(request.FILES.keys()) if request.FILES else "No files")
    
    response_data = {
        "message": "",
        "document_type": "",
        "extracted_text": ""
    }
    
    # Simplified auth check for development - remove or enhance for production
    if not check_auth(request):
        response_data["message"] = "Authentication required"
        return JsonResponse(response_data, status=200)  # Return 200 instead of 401 to avoid CORS issues
    
    if request.method == "POST" and request.FILES.get("pdf"):
        pdf_file = request.FILES["pdf"]
        
        try:
            # Extract text directly from the uploaded file
            extracted_text = extract_text_from_pdf(pdf_file)
            document_type = classify_document(extracted_text)
            
            # Populate response
            response_data["message"] = "PDF processed successfully"
            response_data["document_type"] = document_type
            response_data["extracted_text"] = extracted_text
            
        except Exception as e: 
            response_data["message"] = f"Error processing PDF: {str(e)}"
    else:
        response_data["message"] = "Please upload a PDF file via POST request"
    
    return JsonResponse(response_data)

# Add a health check endpoint
def health_check(request):
    return JsonResponse({"status": "ok"})

# URL patterns
urlpatterns = [
    path("upload/", upload_pdf),
    path("", upload_pdf),  # Root path for easier access
    path("health/", health_check),  # Health check endpoint
]

# Create WSGI application
application = get_wsgi_application()

# Expose as 'app' for Vercel
app = application

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "__main__")
    execute_from_command_line(sys.argv)