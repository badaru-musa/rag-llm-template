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

## Changelog

### v1.0.0
- Initial release
- Multi-provider LLM support
- Vector search with ChromaDB
- Authentication and authorization
- Document processing pipeline
- Docker Compose deployment
