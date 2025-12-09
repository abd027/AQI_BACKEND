"""
Test script for RAG chatbot
Run with: python test_rag.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from aqi.rag import AQIRAGSystem

def test_rag():
    print("=" * 50)
    print("Testing AQI RAG System")
    print("=" * 50)
    
    # Test initialization
    print("\n1. Testing initialization...")
    rag = AQIRAGSystem()
    init_result = rag._initialize()
    print(f"   Result: {'✓ SUCCESS' if init_result else '✗ FAILED'}")
    
    if not init_result:
        print("\n❌ RAG system failed to initialize.")
        print("Please check:")
        print("  - HUGGINGFACEHUB_API_TOKEN is set in .env")
        print("  - All dependencies are installed")
        return
    
    # Test query (general knowledge)
    print("\n2. Testing general knowledge query...")
    question = "What are the health effects of PM2.5?"
    print(f"   Question: {question}")
    answer = rag.query(question)
    print(f"   Answer: {answer[:200]}...")
    
    print("\n✅ All tests passed!")
    print("\nNow try the chatbot in the web interface:")
    print("  1. Login to your app")
    print("  2. Click the chat button (bottom-right)")
    print("  3. Ask questions about AQI")

if __name__ == "__main__":
    test_rag()
