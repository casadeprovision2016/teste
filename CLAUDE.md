# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a monolithic document processing system built in Python that processes PDF documents (primarily "editais" - government procurement documents) using AI. The system uses FastAPI for the web API, Celery for asynchronous processing, Redis for queuing, and Ollama with Llama 3.2 for AI analysis.

## Architecture
- **API Layer**: FastAPI server (`app/main.py`) with JWT authentication
- **Processing Layer**: Celery workers (`app/workoer.py`) for async PDF processing  
- **AI Engine**: Ollama + Llama 3.2 3B model for document analysis
- **Storage**: SQLite database + organized file system storage
- **Queue**: Redis for task queuing and caching

## Key Commands

### Docker Operations
```bash
# Build and start all services
docker-compose build
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale app-worker=8

# Stop services
docker-compose down
```

### Development
```bash
# Install dependencies
pip install -r requiriments.txt

# Run API server locally
python app/main.py

# Run Celery worker locally
celery -A app.worker worker --loglevel=info --concurrency=4

# Health check
curl http://localhost:8000/health
```

### Monitoring
- **API Documentation**: http://localhost:8000/docs
- **Flower Dashboard**: http://localhost:5555 (admin/admin123)
- **Redis**: localhost:6379

## File Structure & Storage
Documents are organized as: `storage/editais/{ANO}/{UASG}/{NUMERO_PREGAO}/`
Processed results stored as: `storage/processados/{task_id}/resultado.json`

## Key Components

### Main Application (`app/main.py`)
- FastAPI endpoints for upload, status checking, and result retrieval
- JWT authentication with user isolation
- Async file upload handling
- Database operations with SQLAlchemy

### Worker Process (`app/workoer.py`)
- Celery task for PDF processing with progress tracking
- Integration with AI services (Docling, Llama)
- Table extraction and risk analysis
- Result persistence and callback handling
- Error handling with retry logic

### Dependencies
Key libraries include FastAPI, Celery, Redis, SQLAlchemy, Ollama, Docling, and various PDF processing tools (PyPDF2, pdfplumber, camelot-py, tabula-py).

## API Endpoints
- `POST /api/v1/editais/processar` - Upload and queue PDF for processing
- `GET /api/v1/editais/status/{task_id}` - Check processing status
- `GET /api/v1/editais/resultado/{task_id}` - Get processing results
- `GET /api/v1/editais` - List user's documents
- `DELETE /api/v1/editais/{task_id}/cancelar` - Cancel processing
- `POST /api/v1/editais/{task_id}/reprocessar` - Retry failed processing

## Performance Characteristics
- Designed for ~50 documents/day processing capacity
- ~8 minutes average processing time per document
- 4 parallel Celery workers by default
- Uses Llama 3.2 3B quantized model for efficiency
- Requires ~16GB RAM for optimal performance

## Development Notes
- Note: There's a typo in the filename `workoer.py` (should be `worker.py`)
- The system includes comprehensive error handling and retry mechanisms
- Portuguese language documentation is included in `teste.md`
- HTML visualization dashboard available in `html/index.html`