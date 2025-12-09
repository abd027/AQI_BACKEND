"""
Test RAG query functionality
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from aqi.rag import AQIRAGSystem

print("\n=== TESTING RAG QUERY ===\n")

# Create RAG instance
rag = AQIRAGSystem()

# Test query
question = "What is AQI and how is air quality measured?"
print(f"Question: {question}\n")

try:
    answer = rag.query(question)
    print(f"Answer: {answer}\n")
    
    if "Sorry, the AI system is not properly configured" in answer:
        print("✗ ERROR: Received configuration error message")
    else:
        print("✓ SUCCESS: Received valid answer")
except Exception as e:
    print(f"✗ EXCEPTION: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETE ===\n")
