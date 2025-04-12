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
    DEBUG=False,
    ROOT_URLCONF=__name__,
    SECRET_KEY='1_d0nt_kn0w_what_t0_keep',
    ALLOWED_HOSTS=['*'],
)

# Function to process PDF and extract text using PDFMiner
def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PDFMiner"""
    output_string = io.StringIO()
    with open(pdf_path, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)
    
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
    print("Request method:", request.method)
    print("Request headers:", request.headers)
    print("Files in request:", request.FILES)
    print("File keys:", list(request.FILES.keys()) if request.FILES else "No files")
    
    if request.method == "POST" and request.FILES.get("pdf"):
        pdf_file = request.FILES["pdf"]
        pdf_path = f"/tmp/{pdf_file.name}"

        response_data = {
            "message": "",
            "document_type": "",
            "extracted_text": ""
        }
        
        try:
            # Save the uploaded file
            with open(pdf_path, "wb") as f:
                for chunk in pdf_file.chunks():
                    f.write(chunk)
            
            # Extract and classify text
            extracted_text = extract_text_from_pdf(pdf_path)
            document_type = classify_document(extracted_text)
            
            # Populate response
            response_data["message"] = "PDF processed successfully"
            response_data["document_type"] = document_type
            response_data["extracted_text"] = extracted_text
            
        except Exception as e: 
            response_data["message"] = f"Error processing PDF: {str(e)}"
        
        finally:
            # Clean up temporary file
            try:
                os.remove(pdf_path)
            except:
                pass
        
        return JsonResponse(response_data)
    
    return JsonResponse({
        "message": "Please upload a PDF file via POST request",
        "document_type": "",
        "extracted_text": ""
    })

# URL patterns
urlpatterns = [
    path("upload/", upload_pdf),
    path("", upload_pdf),  # Add root path for easier access
]

# Create WSGI application
application = get_wsgi_application()

# Expose as 'app' for Vercel
app = application

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "__main__")
    execute_from_command_line(sys.argv)