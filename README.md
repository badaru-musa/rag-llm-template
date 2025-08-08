# RAG LLM Template

A comprehensive, production-ready template for building Retrieval-Augmented Generation (RAG) applications with multiple LLM providers, vector databases, and a modern FastAPI backend.

## Features

### 🚀 **Multi-Provider LLM Support**
- **Azure OpenAI** (default)
- **OpenAI**
- **Anthropic Claude**
- **Google Gemini**
- **Local Models** (extensible)

### 🧠 **Flexible Embedding Services**
- **Local Embeddings** (sentence-transformers, default)
- **OpenAI Embeddings**
- **Azure OpenAI Embeddings**

### 🗄️ **Dual Database Architecture**
- **ChromaDB** for vector storage and NoSQL operations
- **PostgreSQL** for relational data (users, conversations, metadata)
- **Redis** for caching and session management

### 📚 **Document Processing**
- Support for PDF, DOCX, TXT, and Markdown files
- Intelligent text chunking with overlap
- Automatic metadata extraction
- File upload validation and security

### 🔐 **Authentication & Authorization**
- JWT-based authentication
- Role-based access control (Admin, User, Viewer)
- Secure password hashing with bcrypt
- Session management

### 🎛️ **RAG Configuration**
- Toggle vector search on/off per conversation
- Configurable similarity thresholds
- Adjustable chunk retrieval limits
- Custom prompts and system messages

### 🐳 **Production Ready**
- Docker Compose orchestration
- Health checks and monitoring
- Comprehensive logging
- Error handling and validation
- Structured configuration management

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### 1. Clone the Repository
```bash
git clone <repository-url>
cd rag-llm-template
```

### 2. Environment Configuration
```bash
# Copy the example environment file
cp .env.example .env

# Edit the environment file with your settings
nano .env
```

**Required Configuration:**
```bash
# Azure OpenAI (default LLM provider)
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Database
DATABASE_URL=postgresql://postgres:password@db:5432/ragllm

# Security
SECRET_KEY=your-secret-key-here
```

### 3. Start the Application
```bash
# Build and start all services
docker compose up --build

# Or run in detached mode
docker compose up --build -d
```

> **Note:** This template is configured for direct access on port 8000 for internal testing. For production deployments with nginx reverse proxy, see `docker/README_nginx.md`.

### 4. Access the Application
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Application:** http://localhost:8000

## Architecture

### Directory Structure
```
rag-llm-template/
├── app/                    # Main application code
│   ├── auth/              # Authentication services
│   ├── db/                # Database models and connections
│   ├── embeddings/        # Embedding services
│   ├── enums/             # Enumerations
│   ├── generation/        # LLM services and chat logic
│   ├── ingestion/         # Document processing
│   ├── middleware/        # FastAPI middleware
│   ├── prompts/           # System prompts and templates
│   ├── retrieval/         # Vector search and retrieval
│   ├── schema/            # Pydantic schemas
│   ├── utils/             # Utility functions
│   ├── views/             # API endpoints
│   └── main.py           # FastAPI application
├── data/                  # Data storage
│   ├── documents/         # Uploaded documents
│   ├── vector_store/      # ChromaDB data
│   └── db/               # Database files
├── docker/               # Docker configuration
├── docs/                 # Documentation
├── migrations/           # Database migrations
├── Notebooks/            # Jupyter notebooks
├── tests/               # Test files
├── docker-compose.yml   # Docker services
├── Dockerfile           # Application container
└── requirements.txt     # Python dependencies
```

### Service Architecture
```
                       ┌─────────────────┐
                       │   FastAPI App   │
                       │  (Main Service) │
                       │   Port: 8000    │
                       └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
       ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
       │   PostgreSQL    │ │    ChromaDB     │ │     Redis       │
       │   (User Data)   │ │ (Vector Store)  │ │   (Caching)     │
       │   Port: 5432    │ │   Port: 8001    │ │   Port: 6379    │
       └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Configuration Options

### LLM Providers
Switch between different LLM providers by changing the `LLM_PROVIDER` environment variable:

```bash
# Azure OpenAI (default)
LLM_PROVIDER=azure_openai

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key

# Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key

# Google Gemini
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_google_key
```

### Embedding Providers
Configure embedding services:

```bash
# Local embeddings (default)
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# OpenAI embeddings
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your_openai_key

# Azure OpenAI embeddings
EMBEDDING_PROVIDER=azure_openai
AZURE_EMBEDDING_DEPLOYMENT_NAME=text-embedding-ada-002
```

### RAG Settings
Fine-tune RAG behavior:

```bash
# Vector search toggle
USE_VECTOR_SEARCH=True

# Retrieval parameters
MAX_CHUNKS_RETURNED=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
SIMILARITY_THRESHOLD=0.7
```

## API Usage

### Authentication
```bash
# Register a new user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "full_name": "Test User"
  }'

# Login
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=SecurePass123!"
```

### Document Upload
```bash
# Upload a document
curl -X POST "http://localhost:8000/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf" \
  -F "title=My Document"
```

### Chat
```bash
# Send a chat message
curl -X POST "http://localhost:8000/chat/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the main topic of my documents?",
    "use_vector_search": true,
    "max_chunks": 5
  }'
```

## Development

### Local Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env

# Run database migrations (if needed)
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_auth.py
```

### Adding New LLM Providers
1. Create a new service class inheriting from `BaseLLMService` in `app/generation/llm_factory.py`
2. Add the provider to the `LLMProvider` enum in `app/enums/__init__.py`
3. Register the service in the `LLMFactory`
4. Add configuration options in `config.py`

### Adding New Document Types
1. Extend the `DocumentProcessor` class in `app/ingestion/document_processor.py`
2. Add the file extension to `FileType` enum
3. Update the allowed extensions in configuration

## Monitoring & Observability

### Health Checks
- **Basic:** `GET http://localhost:8000/health/`
- **Detailed:** `GET http://localhost:8000/health/detailed`
- **Ping:** `GET http://localhost:8000/health/ping`

### Logging
Logs are structured and include:
- Request IDs for tracing
- Performance metrics
- Error details
- User actions (anonymized)

### Metrics
The application exposes metrics for:
- Request latency
- Error rates
- Document processing times
- Vector search performance

## Deployment

### Production Deployment
1. **Environment Variables:** Ensure all production secrets are configured
2. **SSL/TLS:** Configure HTTPS with a reverse proxy (nginx, traefik, etc.)
3. **Database:** Use managed PostgreSQL service
4. **Storage:** Configure persistent volumes for data
5. **Monitoring:** Set up application monitoring
6. **Backup:** Implement backup strategies for data

### Scaling Considerations
- **Horizontal Scaling:** Multiple FastAPI instances behind load balancer
- **Database:** Read replicas for improved performance
- **Vector Store:** ChromaDB clustering for large datasets
- **Caching:** Redis cluster for high availability

## Security

### Best Practices Implemented
- ✅ JWT tokens with expiration
- ✅ Password hashing with bcrypt
- ✅ Input validation and sanitization
- ✅ File upload restrictions
- ✅ CORS configuration
- ✅ Rate limiting ready
- ✅ Secure headers

### Additional Security Recommendations
- Configure rate limiting
- Implement API key management
- Set up WAF (Web Application Firewall)
- Enable audit logging
- Regular security updates

## Troubleshooting

### Common Issues

**1. ChromaDB Connection Failed**
```bash
# Check if ChromaDB service is running
docker compose ps chromadb

# Check logs
docker compose logs chromadb
```

**2. Database Connection Error**
```bash
# Verify PostgreSQL is running
docker compose ps db

# Check database logs
docker compose logs db
```

**3. LLM API Errors**
- Verify API keys are correct
- Check API quotas and limits
- Ensure proper model permissions

**4. File Upload Issues**
- Check file size limits
- Verify file type restrictions
- Ensure proper permissions

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions and support:
- 📧 Email: [your-email@example.com]
- 💬 Discussions: GitHub Discussions
- 🐛 Issues: GitHub Issues
- 📖 Documentation: `/docs` endpoint when running

## Changelog

### v1.0.0
- Initial release
- Multi-provider LLM support
- Vector search with ChromaDB
- Authentication and authorization
- Document processing pipeline
- Docker Compose deployment

---

**Built with ❤️ for the AI community**
