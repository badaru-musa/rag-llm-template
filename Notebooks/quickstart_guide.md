# RAG LLM Template - Quick Start Guide

This notebook demonstrates how to use the RAG LLM Template for building a retrieval-augmented generation system.

## 1. Environment Setup

First, make sure you have the application running:

```bash
docker compose up --build
```

## 2. API Client Setup

```python
import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

# Helper class for API interactions
class RAGClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.token = None
        self.session = requests.Session()
    
    def register(self, username, email, password, full_name=None):
        """Register a new user"""
        data = {
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name or username
        }
        response = self.session.post(f"{self.base_url}/auth/register", json=data)
        return response.json()
    
    def login(self, username, password):
        """Login and store token"""
        data = {"username": username, "password": password}
        response = self.session.post(
            f"{self.base_url}/auth/login",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        result = response.json()
        if "access_token" in result:
            self.token = result["access_token"]
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return result
    
    def upload_document(self, file_path, title=None):
        """Upload a document"""
        with open(file_path, 'rb') as f:
            files = {"file": f}
            data = {"title": title} if title else {}
            response = self.session.post(
                f"{self.base_url}/documents/upload",
                files=files,
                data=data
            )
        return response.json()
    
    def chat(self, message, use_vector_search=True, max_chunks=5):
        """Send a chat message"""
        data = {
            "message": message,
            "use_vector_search": use_vector_search,
            "max_chunks": max_chunks
        }
        response = self.session.post(f"{self.base_url}/chat/", json=data)
        return response.json()
    
    def search_documents(self, query, max_results=5):
        """Search documents"""
        params = {"query": query, "max_results": max_results}
        response = self.session.post(f"{self.base_url}/chat/search", params=params)
        return response.json()
    
    def get_conversations(self):
        """Get conversation list"""
        response = self.session.get(f"{self.base_url}/chat/conversations")
        return response.json()
    
    def get_documents(self):
        """Get document list"""
        response = self.session.get(f"{self.base_url}/documents/")
        return response.json()
```

## 3. Basic Usage Example

```python
# Initialize client
client = RAGClient()

# Register a new user (or use existing account)
try:
    register_result = client.register(
        username="demo_user",
        email="demo@example.com",
        password="SecurePass123!",
        full_name="Demo User"
    )
    print("Registration successful:", register_result)
except Exception as e:
    print("User might already exist, trying to login...")

# Login
login_result = client.login("demo_user", "SecurePass123!")
print("Login result:", login_result)

# Check if login was successful
if client.token:
    print("✅ Successfully authenticated!")
else:
    print("❌ Authentication failed")
    exit()
```

## 4. Document Upload and Processing

```python
# Create a sample document
sample_document = """
# Machine Learning Fundamentals

Machine learning is a subset of artificial intelligence that focuses on the development
of algorithms and statistical models that enable computer systems to improve their
performance on a specific task through experience.

## Types of Machine Learning

1. **Supervised Learning**: Uses labeled training data to learn a mapping function
   from input variables to output variables.

2. **Unsupervised Learning**: Finds hidden patterns in data without labeled examples.

3. **Reinforcement Learning**: Learns through interaction with an environment using
   rewards and penalties.

## Applications

Machine learning has numerous applications including:
- Natural Language Processing
- Computer Vision
- Recommendation Systems
- Fraud Detection
- Autonomous Vehicles
"""

# Save to file
with open("ml_fundamentals.md", "w") as f:
    f.write(sample_document)

# Upload the document
upload_result = client.upload_document("ml_fundamentals.md", "Machine Learning Fundamentals")
print("Upload result:", upload_result)

# List all documents
documents = client.get_documents()
print(f"Total documents: {len(documents)}")
for doc in documents:
    print(f"- {doc['title']} (Status: {doc['status']})")
```

## 5. Chat with RAG

```python
# Wait a moment for document processing
import time
time.sleep(2)

# Chat with vector search enabled
print("🤖 Chatting with RAG enabled:")
rag_response = client.chat(
    "What are the three types of machine learning?",
    use_vector_search=True
)

print("Response:", rag_response["message"])
print(f"Sources used: {len(rag_response['sources'])}")
for i, source in enumerate(rag_response["sources"]):
    print(f"  Source {i+1}: Score {source['score']:.3f}")
    print(f"    Content: {source['content'][:100]}...")

# Chat without vector search
print("\n🤖 Chatting without RAG:")
no_rag_response = client.chat(
    "What are the three types of machine learning?",
    use_vector_search=False
)
print("Response:", no_rag_response["message"])
```

## 6. Document Search

```python
# Search documents directly
search_results = client.search_documents("supervised learning")
print(f"Search results for 'supervised learning': {len(search_results)} chunks found")

for result in search_results:
    print(f"- Score: {result['score']:.3f}")
    print(f"  Content: {result['content'][:150]}...")
    print()
```

## 7. Conversation Management

```python
# Get conversation history
conversations = client.get_conversations()
print(f"Total conversations: {len(conversations)}")

for conv in conversations:
    print(f"- {conv['title']}: {conv['message_count']} messages")
```

## 8. Advanced Features

### Custom Prompts and Context
```python
# Ask a more complex question
complex_response = client.chat(
    "Compare supervised and unsupervised learning, and give me examples of each.",
    use_vector_search=True,
    max_chunks=3
)

print("Complex query response:")
print(complex_response["message"])
```

### Document Analysis
```python
# Ask for document analysis
analysis_response = client.chat(
    "Summarize the main topics covered in my documents.",
    use_vector_search=True
)

print("Document analysis:")
print(analysis_response["message"])
```

## 9. Configuration Examples

### Different LLM Providers
If you want to switch LLM providers, update your `.env` file:

```bash
# For OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key

# For Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key

# For Google Gemini
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_google_key
```

### RAG Configuration
```bash
# Adjust RAG behavior
USE_VECTOR_SEARCH=True
MAX_CHUNKS_RETURNED=5
SIMILARITY_THRESHOLD=0.7
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## 10. Monitoring and Debugging

```python
# Check application health
health_response = requests.get(f"{BASE_URL}/health/detailed")
print("Application health:", health_response.json())

# Check chat statistics
if client.token:
    headers = {"Authorization": f"Bearer {client.token}"}
    stats_response = requests.get(f"{BASE_URL}/chat/stats", headers=headers)
    print("Chat statistics:", stats_response.json())
```

## Best Practices

1. **Document Preparation**: Clean and structure your documents for better chunking
2. **Chunk Size**: Adjust chunk size based on your document types
3. **Similarity Threshold**: Fine-tune for your specific use case
4. **Context Management**: Use conversation IDs to maintain context
5. **Error Handling**: Always handle API errors gracefully

## Troubleshooting

### Common Issues:
1. **Document processing failed**: Check file format and size
2. **No relevant chunks found**: Lower similarity threshold
3. **API authentication errors**: Verify token is valid
4. **Slow responses**: Check LLM provider status and quotas

### Debug Mode:
Enable debug logging by setting `DEBUG=True` in your environment.

## Next Steps

- Upload your own documents
- Experiment with different LLM providers
- Customize prompts for your specific use case
- Integrate with your existing applications
- Deploy to production with proper configuration

Happy building! 🚀
