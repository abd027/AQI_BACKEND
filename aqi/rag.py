import os
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings

# Configure logging
logger = logging.getLogger(__name__)

class AQIRAGSystem:
    """RAG System for AQI data with lazy initialization"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AQIRAGSystem, cls).__new__(cls)
        return cls._instance
    
    def _initialize(self):
        """Lazy initialization of RAG components"""
        logger.info(f"_initialize called. Current _initialized state: {self._initialized}")
        
        if self._initialized:
            logger.info("RAG system already initialized, returning True")
            return True
            
        try:
            logger.info("Starting RAG system initialization...")
            # Import here to avoid import-time failures
            from langchain_huggingface import HuggingFaceEndpointEmbeddings
            from langchain_chroma import Chroma
            from huggingface_hub import InferenceClient
            
            self.api_token = getattr(settings, 'HUGGINGFACEHUB_API_TOKEN', '')
            logger.info(f"API Token loaded: {bool(self.api_token)} (length: {len(self.api_token) if self.api_token else 0})")
            
            if not self.api_token:
                logger.error("HUGGINGFACEHUB_API_TOKEN not found in settings. Please add it to your .env file.")
                return False
                
            logger.info("Initializing RAG system...")
            
            # Embedding Model (using cloud-based HuggingFace API)
            logger.info("Setting up cloud-based embedding model via HuggingFace API...")
            self.embedding_model = HuggingFaceEndpointEmbeddings(
                model="sentence-transformers/all-mpnet-base-v2",
                huggingfacehub_api_token=self.api_token
            )
            logger.info("Embedding model configured successfully")
            
            # Vector Store (ChromaDB)
            persist_dir = os.path.join(settings.BASE_DIR, "chroma_db")
            logger.info(f"Setting up ChromaDB at {persist_dir}")
            self.vector_store = Chroma(
                collection_name="aqi_data",
                embedding_function=self.embedding_model,
                persist_directory=persist_dir
            )
            logger.info("ChromaDB initialized successfully")
            
            # LLM - Using direct InferenceClient
            logger.info("Setting up LLM client")
            self.llm_client = InferenceClient(token=self.api_token)
            self.llm_model = "meta-llama/Llama-3.3-70B-Instruct"
            logger.info("LLM client initialized successfully")
            
            self._initialized = True
            logger.info("AQI RAG System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG System: {str(e)}", exc_info=True)
            self._initialized = False
            return False

    def ingest_data(self, aqi_data: Dict[str, Any]) -> bool:
        """Convert AQI data into documents and store in ChromaDB"""
        if not self._initialize():
            logger.error("Cannot ingest data - RAG system not initialized")
            return False
            
        try:
            from langchain_core.documents import Document
            
            documents = []
            
            location = aqi_data.get('location', {})
            city = location.get('city', 'Unknown City')
            lat = location.get('lat')
            lon = location.get('lon')
            current = aqi_data.get('current', {})
            aqi_info = aqi_data.get('aqi', {})
            
            # Create a textual representation of the current AQI status
            content = f"""
Location: {city} (Lat: {lat}, Lon: {lon})
Current AQI: {aqi_info.get('uaqi', {}).get('value', 'N/A') if isinstance(aqi_info.get('uaqi'), dict) else 'N/A'}
Category: {aqi_info.get('uaqi', {}).get('category', 'N/A') if isinstance(aqi_info.get('uaqi'), dict) else 'N/A'}
Dominant Pollutant: {aqi_data.get('dominant_pollutant', 'N/A')}

Pollutants:
PM2.5: {current.get('pm2_5', 'N/A')}
PM10: {current.get('pm10', 'N/A')}
Ozone: {current.get('ozone', 'N/A')}
NO2: {current.get('nitrogen_dioxide', 'N/A')}
SO2: {current.get('sulphur_dioxide', 'N/A')}
CO: {current.get('carbon_monoxide', 'N/A')}

Health Recommendations:
{', '.join(aqi_data.get('health_recommendations', []))}
            """
            
            # Metadata for filtering
            metadata = {
                "city": city,
                "lat": lat,
                "lon": lon,
                "type": "current_aqi",
                "timestamp": current.get('time', '')
            }
            
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
            
            # Add to vector store
            self.vector_store.add_documents(documents)
            logger.info(f"Ingested AQI data for {city}")
            return True
            
        except Exception as e:
            logger.error(f"Error ingesting data: {str(e)}", exc_info=True)
            return False

    def query(self, question: str) -> str:
        """Query the RAG system"""
        if not self._initialize():
            return "Sorry, the AI system is not properly configured. Please ensure HUGGINGFACEHUB_API_TOKEN is set in the .env file."
            
        try:
            context = "No specific AQI data found in database for this query."
            
            # Try to retrieve context from vector store, but continue if it fails
            try:
                retriever = self.vector_store.as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": 3}
                )
                
                # Get relevant documents
                docs = retriever.invoke(question)
                if docs:
                    context = "\n\n".join([d.page_content for d in docs])
                    logger.info(f"Retrieved context for query '{question}': {context[:100]}...")
            except Exception as e:
                logger.warning(f"Vector store retrieval failed (using LLM without context): {str(e)}")
                context = "No specific AQI data found in database for this query."
            
            # Build messages for chat completion
            messages = [
                {
                    "role": "system",
                    "content": """You are an AQI (Air Quality Index) assistant. Your job is to help users understand air quality data and provide health recommendations.

INSTRUCTIONS:
- If context data is provided, use it to answer the question accurately
- If no context is available, use your general knowledge about air quality
- Provide concise,informative answers
- Include health recommendations when relevant
- Be helpful and user-friendly"""
                },
                {
                    "role": "user",
                    "content": f"""CONTEXT:
{context}

QUESTION:
{question}

Please answer the question using the context if available, otherwise use your general knowledge about air quality."""
                }
            ]
            
            # Generate answer using chat completion
            response = self.llm_client.chat_completion(
                messages=messages,
                model=self.llm_model,
                max_tokens=512,
                temperature=0.7
            )
            
            # Extract the response text
            answer = response.choices[0].message.content
            return answer
            
        except Exception as e:
            logger.error(f"Error querying RAG system: {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error: {str(e)}. Please try again later."


