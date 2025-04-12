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
def classify_document(text, expected_type=None):
    """
    Classify document and verify if it matches expected type
    Returns: {
        "document_type": detected type,
        "confidence": confidence score (0-100),
        "matches_expected": True/False if expected_type is provided,
        "keywords_found": list of keywords found
    }
    """
    categories = {
        "permissionLetter": [
            "permission letter", "signed letter", "approval", "permission to undertake", 
            "authorized to pursue", "internship permission", "grant permission",
            "permission is hereby granted", "letter of permission"
        ],
        "offerLetter": [
            "offer letter", "employment offer", "job offer", "pleased to offer", 
            "offer of internship", "internship offer", "position of intern",
            "formal offer", "offer of employment", "internship opportunity"
        ],
        "completionCertificate": [
            "completion certificate", "certification", "internship completed",
            "certificate of completion", "successfully completed", "this certifies that",
            "has successfully completed", "internship program completion"
        ],
        "internshipReport": [
            "internship report", "work summary", "project report", "project details",
            "tasks performed", "internship summary", "summary of work", 
            "project completed", "work performed", "technical report"
        ],
        "studentFeedback": [
            "student feedback", "internship experience", "review", "my experience",
            "student review", "my internship", "learning experience", "skills gained",
            "my learning", "personal growth", "student reflection"
        ],
        "employerFeedback": [
            "employer feedback", "performance review", "student evaluation", 
            "evaluation of intern", "intern performance", "assessment of work",
            "feedback on performance", "supervisor feedback", "mentor assessment",
            "performance assessment"
        ]
    }
    
    results = {}
    max_score = 0
    best_category = "unknown"
    keywords_found = []
    
    # Convert text to lowercase for case-insensitive matching
    text_lower = text.lower()
    
    # Check each category
    for category, keywords in categories.items():
        category_score = 0
        category_keywords = []
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                category_score += 1
                category_keywords.append(keyword)
        
        # Calculate confidence as percentage of keywords found
        confidence = int((category_score / len(keywords)) * 100) if keywords else 0
        
        # Store results for this category
        results[category] = {
            "score": category_score,
            "confidence": confidence,
            "keywords": category_keywords
        }
        
        # Track the best category
        if category_score > max_score:
            max_score = category_score
            best_category = category
            keywords_found = category_keywords
    
    # Calculate confidence for best match
    best_confidence = results[best_category]["confidence"] if best_category in results else 0
    
    # Check if it matches expected type
    matches_expected = False

    if expected_type:
        if expected_type == best_category:
            matches_expected = True
        elif best_category == "unknown" and expected_type in categories:
        # Only give benefit of doubt if we found at least one relevant keyword
            if len(keywords_found) > 0:  # This checks if we found ANY relevant keywords
                matches_expected = True
            else:
                matches_expected = False  # Reject documents with no relevant keywords
    
    return {
        "document_type": best_category,
        "confidence": best_confidence,
        "matches_expected": matches_expected,
        "keywords_found": keywords_found
    }

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
        "extracted_text": "",
        "is_valid": False,
        "confidence": 0,
        "keywords_found": []
    }
    
    # Simplified auth check for development
    if not check_auth(request):
        response_data["message"] = "Authentication required"
        return JsonResponse(response_data, status=200)
    
    if request.method == "POST" and request.FILES.get("pdf"):
        pdf_file = request.FILES["pdf"]
        expected_type = request.POST.get("document_type", None)
        
        try:
            # Extract text from PDF
            extracted_text = extract_text_from_pdf(pdf_file)
            
            # Get enhanced classification result
            classification = classify_document(extracted_text, expected_type)
            
            # Determine if document is valid
            # In your upload_pdf function
            is_valid = classification["matches_expected"]
            if not is_valid and classification["document_type"] == "unknown":
                if len(classification["keywords_found"]) == 0:
                    message = f"Cannot verify this as a {expected_type} document. No relevant content found."
                else:
                    message = f"Unable to verify this as a {expected_type} document. Insufficient relevant content."
            
            # Populate response
            response_data["message"] = message
            response_data["document_type"] = classification["document_type"]
            response_data["extracted_text"] = extracted_text
            response_data["is_valid"] = is_valid
            response_data["confidence"] = classification["confidence"]
            response_data["keywords_found"] = classification["keywords_found"]
            
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