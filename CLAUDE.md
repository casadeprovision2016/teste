# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an enterprise-grade monolithic document processing system for Brazilian government procurement documents ("editais"). Built with Python, it processes PDF documents using AI (Ollama + Llama 3.2) and IBM Docling for structured data extraction, table analysis, risk assessment, and opportunity identification.

## Architecture
- **API Layer**: FastAPI server with JWT auth, user management, quotas
- **Processing Engine**: Celery workers with 14-stage processing pipeline
- **AI Stack**: Ollama + Llama 3.2 3B + IBM Docling for document understanding
- **Database**: SQLite (production-ready with PostgreSQL support)
- **Storage**: Organized file system (`{ANO}/{UASG}/{PREGAO}`) + Redis caching
- **Queue Management**: Redis with Flower monitoring dashboard

## Key Commands

### Quick Start (Production Ready)
```bash
# Deploy entire system with one command
bash scripts/deploy.sh

# Or use Makefile shortcuts
make build && make up

# Run comprehensive test suite
make test
python run_tests.py
```

### Docker Operations
```bash
# Build and start all services
docker-compose build
docker-compose up -d

# Check service status
docker-compose ps

# View logs (all services or specific)
docker-compose logs -f
docker-compose logs -f app-worker

# Scale workers based on load
docker-compose up -d --scale app-worker=8

# Clean restart
docker-compose down && docker-compose up -d
```

### Development & Testing
```bash
# Install dependencies
pip install -r requiriments.txt

# Run API server locally
python app/main.py

# Run single test file
pytest tests/test_system.py -v

# Run tests with coverage
pytest tests/ --cov=app --cov-report=html

# Create admin user
python -c "from app.core.database import init_db; init_db()"
```

### Database Operations
```bash
# Initialize database
docker-compose exec app-api python -c "from app.core.database import init_db; init_db()"

# Database shell
make shell-db

# Backup database
make backup
```

## Monitoring & Health Checks
- **API Documentation**: http://localhost:8000/docs
- **Flower Dashboard**: http://localhost:5555 (admin/admin123)
- **Health Endpoint**: http://localhost:8000/health
- **System Metrics**: `GET /api/v1/admin/metrics/system`

## Project Structure
The codebase follows a modular architecture with clear separation of concerns:

```
app/
├── main.py              # FastAPI application entry point
├── worker.py            # Celery worker with 14-stage processing
├── models.py            # SQLAlchemy models (8 tables)
├── schemas.py           # Pydantic request/response models
├── core/
│   ├── config.py        # Centralized settings with 50+ options
│   ├── database.py      # DB session management + SQLite optimizations
│   └── security.py      # JWT auth, password hashing, user verification
├── api/endpoints/
│   └── auth.py          # Authentication endpoints
├── services/
│   ├── ai_engine.py     # Ollama + Docling integration
│   └── edital_processor.py # 14-stage processing pipeline
└── utils/
    └── file_manager.py  # Organized file storage management
```

## Processing Pipeline (14 Stages)
The system uses a sophisticated processing pipeline defined in `ProcessingStage` enum:
1. **Validation** - File type, size, format validation
2. **Text Extraction** - Basic PDF text extraction
3. **OCR Processing** - For image-based PDFs (Portuguese + English)
4. **Table Detection** - AI-powered table identification
5. **Table Extraction** - Structured table data extraction
6. **AI Preprocessing** - Text chunking and preparation
7. **AI Analysis** - Llama 3.2 semantic analysis
8. **Structure Extraction** - Edital metadata extraction
9. **Risk Analysis** - Business risk identification
10. **Opportunity Identification** - Business opportunity analysis
11. **Quality Validation** - Result quality scoring
12. **Result Compilation** - Final result assembly
13. **Storage** - Persistent storage of results
14. **Notification** - Webhook callbacks

## Database Schema
The system uses 8 main tables with comprehensive relationships:
- **Users**: Authentication, quotas, API keys
- **Editais**: Main document records with processing status
- **Products**: Extracted product/service items from tables
- **Risks**: Identified risks with probability/impact scoring
- **Opportunities**: Business opportunities with ROI estimates
- **ProcessingLogs**: Detailed processing stage logs
- **APILogs**: Request/response tracking
- **SystemMetrics**: Performance monitoring data

## API Endpoints Structure
All endpoints follow `/api/v1/` pattern with comprehensive auth:
- **Auth**: `/auth/register`, `/auth/token` (JWT)
- **Editais**: CRUD operations with status tracking
- **Admin**: System metrics and management
- **Users**: Profile management

## Configuration Management
Environment configuration is centralized in `app/core/config.py` with 50+ settings:
- Security keys (SECRET_KEY, JWT_SECRET_KEY)
- AI model settings (MODEL_NAME, OLLAMA_HOST)
- Processing limits (DAILY_PROCESSING_LIMIT, MAX_CONCURRENT_TASKS)
- Storage paths and limits
- Email notifications (optional)
- Monitoring integration (Sentry, metrics)

## Testing Infrastructure
Comprehensive test suite includes:
- **System Tests**: Full end-to-end processing (`test_system.py`)
- **Performance Tests**: Concurrent processing, large files
- **Security Tests**: Authentication, authorization, injection protection
- **Test Runner**: Automated service checking and test execution

## Deployment & Production
- **Deployment Script**: `scripts/deploy.sh` - One-command production deployment
- **Test Script**: `scripts/test_upload.py` - Upload validation script
- **Makefile**: Common operations shortcuts
- **Docker Multi-stage**: Optimized builds with security (non-root user)
- **Health Checks**: Built-in container health monitoring

## Performance Characteristics
- **Capacity**: 50 documents/day (configurable)
- **Processing Time**: ~8 minutes average per document
- **Concurrency**: 4 parallel workers (scalable)
- **AI Model**: Llama 3.2 3B quantized for efficiency
- **Resource Requirements**: 16GB RAM, 8 CPU cores recommended
- **Quality Score**: 95%+ extraction accuracy target

## Security Features
- JWT authentication with refresh tokens
- User quotas and rate limiting
- API key support for service-to-service
- SQL injection protection
- File hash deduplication
- Comprehensive audit logging
- Non-root Docker containers

## Development Notes
- The system is production-ready with comprehensive error handling
- Portuguese documentation available in `teste.md` and `README.md`
- HTML visualization dashboard in `html/index.html`
- Extensive use of async/await for performance
- Type hints throughout codebase for maintainability
- Comprehensive logging at all levels