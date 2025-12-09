"""
Debug script to test RAG system initialization
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from django.conf import settings
print(f"\n=== TESTING RAG INITIALIZATION ===\n")

# Step 1: Check API Token
print("Step 1: Checking API Token...")
token = getattr(settings, 'HUGGINGFACEHUB_API_TOKEN', '')
if token:
    print(f"   ✓ API Token found: {token[:10]}...{token[-10:]}")
else:
    print("   ✗ API Token NOT FOUND")
    exit(1)

# Step 2: Check imports
print("\nStep 2: Checking package imports...")
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    print("   ✓ langchain_huggingface imported")
except ImportError as e:
    print(f"   ✗ langchain_huggingface FAILED: {e}")
    exit(1)

try:
    from langchain_chroma import Chroma
    print("   ✓ langchain_chroma imported")
except ImportError as e:
    print(f"   ✗ langchain_chroma FAILED: {e}")
    exit(1)

try:
    from huggingface_hub import InferenceClient
    print("   ✓ huggingface_hub imported")
except ImportError as e:
    print(f"   ✗ huggingface_hub FAILED: {e}")
    exit(1)

# Step 3: Test RAG initialization
print("\nStep 3: Testing RAG system initialization...")
try:
    from aqi.rag import AQIRAGSystem
    rag = AQIRAGSystem()
    print("   ✓ RAG instance created")
    
    # Try to initialize
    print("\n   Attempting initialization (this may take time on first run)...")
    result = rag._initialize()
    
    if result:
        print("   ✓ RAG system initialized successfully!")
    else:
        print("   ✗ RAG system initialization returned False")
        print("   Check the logs above for errors")
except Exception as e:
    print(f"   ✗ RAG initialization FAILED with exception:")
    print(f"   {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETE ===\n")
