"""
Test RAG with cloud-based embeddings
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from aqi.rag import AQIRAGSystem

print("\n=== TESTING CLOUD-BASED RAG ===\n")

# Create RAG instance
rag = AQIRAGSystem()

# Test initialization
print("Testing initialization...")
result = rag._initialize()
print(f"Initialization result: {result}\n")

if result:
    # Test query
    question = "What is AQI?"
    print(f"Question: {question}\n")
    
    try:
        answer = rag.query(question)
        print(f"Answer: {answer}\n")
        
        if "Sorry, the AI system is not properly configured" in answer:
            print("✗ ERROR: Received configuration error message")
        else:
            print("✓ SUCCESS: Chatbot is working!")
    except Exception as e:
        print(f"✗ EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    print("✗ Initialization failed")

print("\n=== TEST COMPLETE ===\n")
