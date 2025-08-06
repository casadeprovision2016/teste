# 📋 Sistema de Processamento de Editais com IA

## 🚀 Visão Geral

Sistema monolítico robusto para processamento automatizado de editais de licitação usando IA local. Processa até 50 editais/dia com extração inteligente de dados, análise de riscos e identificação de oportunidades.

### 🎯 Características Principais

- **Processamento Assíncrono**: Fila com Celery + Redis
- **IA Local**: Llama 3.2 (3B params) + Docling
- **Extração Inteligente**: Tabelas, produtos e estrutura
- **Análise de Riscos**: Identificação automática de riscos
- **API RESTful**: FastAPI com documentação automática
- **Organização Automática**: {ANO}/{UASG}/{PREGAO}
- **Monitoramento**: Flower Dashboard + Métricas

## 📦 Requisitos do Sistema

### Hardware Mínimo
- **CPU**: 4 cores (8 recomendado)
- **RAM**: 16GB (32GB recomendado)
- **Disco**: 100GB SSD
- **GPU**: Opcional (NVIDIA para acelerar IA)

### Software
- Docker 20.10+
- Docker Compose 2.0+
- Git
- 10GB de espaço para modelos IA

## 🛠️ Instalação Rápida

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/edital-processor.git
cd edital-processor
```

### 2. Configure o Ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite com suas configurações
nano .env
```

**Configurações Importantes no .env:**

```env
# Segurança (MUDE ESTAS CHAVES!)
SECRET_KEY=gere-uma-chave-segura-com-32-caracteres-minimo
JWT_SECRET_KEY=outra-chave-segura-para-jwt-32-chars

# Limites de Processamento
DAILY_PROCESSING_LIMIT=50
MAX_CONCURRENT_TASKS=4

# Modelo IA
MODEL_NAME=llama3.2:3b
MODEL_MAX_TOKENS=4096

# Flower Dashboard
FLOWER_PASSWORD=senha-segura-admin
```

### 3. Build e Deploy

```bash
# Construa as imagens Docker
docker-compose build

# Baixe o modelo Llama
docker-compose run --rm ollama ollama pull llama3.2:3b

# Inicie todos os serviços
docker-compose up -d

# Verifique o status
docker-compose ps
```

### 4. Crie o Usuário Admin

```bash
# Acesse o container
docker-compose exec app-api bash

# Execute o script de criação
python -c "
from app.core.database import SessionLocal, init_db
from app.models import User
from app.core.security import get_password_hash

# Initialize database
init_db()

# Create admin user
db = SessionLocal()
admin = User(
    email='admin@example.com',
    username='admin',
    hashed_password=get_password_hash('admin123'),
    full_name='Administrator',
    role='admin',
    is_active=True,
    is_verified=True,
    daily_quota=1000
)
db.add(admin)
db.commit()
print('Admin user created!')
"
```

## 📊 Estrutura do Projeto

```
edital-processor/
├── app/
│   ├── api/
│   │   └── endpoints/       # Endpoints da API
│   ├── core/
│   │   ├── config.py        # Configurações
│   │   ├── database.py      # Conexão DB
│   │   └── security.py      # Autenticação
│   ├── models.py            # Modelos SQLAlchemy
│   ├── schemas.py           # Schemas Pydantic
│   ├── services/
│   │   ├── ai_engine.py     # Motor IA
│   │   ├── pdf_processor.py # Processamento PDF
│   │   └── table_extractor.py # Extração tabelas
│   ├── utils/               # Utilitários
│   ├── worker.py            # Celery tasks
│   └── main.py              # FastAPI app
├── storage/
│   ├── editais/             # PDFs organizados
│   ├── processados/         # Resultados
│   └── temp/                # Arquivos temporários
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── scripts/
│   ├── deploy.sh            # Script de deploy
│   └── test_upload.py       # Teste de upload
└── requirements.txt
```

## 🔧 Uso da API

### Autenticação

```bash
# Obter token JWT
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=admin123"

# Resposta
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Upload de Edital

```bash
# Upload com metadados
curl -X POST http://localhost:8000/api/v1/editais/processar \
  -H "Authorization: Bearer {token}" \
  -F "file=@edital.pdf" \
  -F "ano=2025" \
  -F "uasg=986531" \
  -F "numero_pregao=PE-001-2025"

# Resposta
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Edital adicionado à fila de processamento",
  "progress": 0.0,
  "position_in_queue": 1
}
```

### Verificar Status

```bash
# Consultar status
curl -X GET http://localhost:8000/api/v1/editais/status/{task_id} \
  -H "Authorization: Bearer {token}"

# Resposta
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Processamento em andamento",
  "progress": 45.5,
  "started_at": "2025-01-15T10:30:00"
}
```

### Obter Resultado

```bash
# Baixar resultado
curl -X GET http://localhost:8000/api/v1/editais/resultado/{task_id} \
  -H "Authorization: Bearer {token}"

# Resposta
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "quality_score": 92.5,
  "objeto": "Contratação de serviços de TI",
  "valor_estimado": 500000.00,
  "products_table": [...],
  "risk_analysis": {...},
  "opportunities": [...]
}
```

## 📈 Monitoramento

### Flower Dashboard
- **URL**: http://localhost:5555
- **Login**: admin / {FLOWER_PASSWORD}
- **Recursos**: Monitoramento de filas, workers e tasks

### Health Check
```bash
curl http://localhost:8000/health
```

### Métricas do Sistema
```bash
curl -X GET http://localhost:8000/api/v1/admin/metrics/system \
  -H "Authorization: Bearer {admin_token}"
```

## 🔍 Troubleshooting

### Problema: Modelo IA não carrega

```bash
# Verifique se o modelo foi baixado
docker-compose exec ollama ollama list

# Se não, baixe novamente
docker-compose exec ollama ollama pull llama3.2:3b
```

### Problema: Memória insuficiente

```bash
# Ajuste os limites no docker-compose.yml
services:
  app-worker:
    deploy:
      resources:
        limits:
          memory: 8G  # Reduza se necessário
```

### Problema: Fila travada

```bash
# Reinicie os workers
docker-compose restart app-worker

# Ou limpe a fila (CUIDADO: perde tasks)
docker-compose exec app-api python -c "
from app.worker import app
app.control.purge()
"
```

### Logs e Debug

```bash
# Ver logs de todos os serviços
docker-compose logs -f

# Logs específicos
docker-compose logs -f app-worker
docker-compose logs -f app-api

# Logs detalhados do worker
docker-compose exec app-worker tail -f /app/logs/celery.log
```

## 🚀 Deploy em Produção

### 1. Configurações de Produção

```bash
# .env.production
DEBUG=False
LOG_LEVEL=WARNING
WORKERS=8
CELERY_WORKER_CONCURRENCY=8
```

### 2. Use Docker Swarm ou Kubernetes

```yaml
# docker-stack.yml para Swarm
version: '3.8'
services:
  app-api:
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### 3. Configure Nginx

```nginx
# nginx.conf
upstream api {
    server app-api:8000;
}

server {
    listen 80;
    server_name api.seudominio.com;
    
    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Backup Automático

```bash
# Crie um cronjob
0 2 * * * docker exec edital-api python -c "
from app.utils.backup import backup_database
backup_database('/backups/daily')
"
```

## 🧪 Testes

### Teste de Upload

```bash
# Use o script de teste fornecido
python scripts/test_upload.py sample_edital.pdf
```

### Testes Automatizados

```bash
# Execute os testes
docker-compose exec app-api pytest tests/ -v

# Com cobertura
docker-compose exec app-api pytest tests/ --cov=app --cov-report=html
```

## 📊 Performance

### Métricas Esperadas

| Métrica | Valor |
|---------|-------|
| Editais/dia | 50 |
| Tempo médio/edital | 8-10 min |
| Precisão extração | 95%+ |
| Uptime | 99.9% |
| RAM por worker | 2-4GB |
| CPU por worker | 1-2 cores |

### Otimizações

1. **Cache de IA**: Resultados são cacheados por 24h
2. **Processamento paralelo**: 4 workers simultâneos
3. **Quantização**: Modelo 4-bit para economia de memória
4. **Compressão**: PDFs processados são comprimidos

## 🔐 Segurança

### Checklist de Segurança

- [ ] Altere TODAS as senhas padrão
- [ ] Configure HTTPS com certificado SSL
- [ ] Habilite rate limiting
- [ ] Configure firewall
- [ ] Faça backup regular
- [ ] Monitore logs de acesso
- [ ] Atualize dependências regularmente

### Variáveis Sensíveis

```bash
# Nunca commite estas variáveis!
SECRET_KEY
JWT_SECRET_KEY
DATABASE_URL (se usar PostgreSQL)
SMTP_PASSWORD
SENTRY_DSN
```

## 📝 API Documentation

### Swagger UI
- **URL**: http://localhost:8000/docs
- **Autenticação**: Use o botão "Authorize" com o token JWT

### ReDoc
- **URL**: http://localhost:8000/redoc

### Postman Collection
Importe o arquivo `postman_collection.json` incluído no projeto.

## 🤝 Suporte

### Documentação
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Celery Docs](https://docs.celeryproject.org)
- [Ollama Docs](https://ollama.ai/docs)

### Problemas Comuns

| Problema | Solução |
|----------|---------|
| Out of memory | Reduza MODEL_MAX_TOKENS ou use modelo menor |
| Slow processing | Aumente workers ou adicione GPU |
| Connection refused | Verifique se todos os containers estão rodando |
| Permission denied | Execute com sudo ou ajuste permissões |

## 📄 Licença

Este projeto está sob licença MIT. Veja o arquivo LICENSE para detalhes.

## 🙏 Créditos

- **FastAPI** - Framework web moderno
- **Celery** - Processamento assíncrono
- **Ollama** - Execução local de LLMs
- **Docling** - Extração de documentos por IBM
- **Docker** - Containerização

---

**Desenvolvido com ❤️ para processamento eficiente de editais**