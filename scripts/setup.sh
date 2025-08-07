#!/bin/bash
# scripts/setup.sh
"""
Complete system setup script
"""

set -e

echo "🚀 SISTEMA DE PROCESSAMENTO DE EDITAIS - SETUP COMPLETO"
echo "======================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
print_status "Verificando pré-requisitos..."

if ! command -v docker &> /dev/null; then
    print_error "Docker não está instalado!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose não está instalado!"
    exit 1
fi

print_success "Pré-requisitos verificados!"

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning "Arquivo .env não encontrado, copiando do exemplo..."
    cp .env.example .env
    print_warning "⚠️  Por favor, edite o arquivo .env com suas configurações antes de continuar em produção!"
fi

# Create necessary directories
print_status "Criando diretórios necessários..."
mkdir -p storage/editais storage/processados storage/temp
mkdir -p data logs models cache/docling

# Set permissions
print_status "Configurando permissões..."
chmod -R 755 storage data logs models cache
chmod +x scripts/*.py 2>/dev/null || true
chmod +x scripts/*.sh 2>/dev/null || true

print_success "Estrutura de diretórios criada!"

# Validate Docker Compose configuration
print_status "Validando configuração do Docker Compose..."
docker-compose config > /dev/null

if [ $? -eq 0 ]; then
    print_success "Configuração do Docker Compose válida!"
else
    print_error "Erro na configuração do Docker Compose!"
    exit 1
fi

# Build Docker images
print_status "Construindo imagens Docker..."
docker-compose build --parallel

if [ $? -eq 0 ]; then
    print_success "Imagens Docker construídas com sucesso!"
else
    print_error "Erro ao construir imagens Docker!"
    exit 1
fi

# Start core services (Redis first)
print_status "Iniciando serviços principais..."
docker-compose up -d redis

# Wait for Redis to be ready
print_status "Aguardando Redis..."
sleep 10

# Start Ollama service
print_status "Iniciando Ollama..."
docker-compose up -d ollama

# Wait for Ollama to be ready
print_status "Aguardando Ollama..."
sleep 15

# Pull Llama model
print_status "Baixando modelo Llama 3.2:3b (pode demorar alguns minutos)..."
docker-compose exec -T ollama ollama pull llama3.2:3b

if [ $? -eq 0 ]; then
    print_success "Modelo Llama 3.2:3b baixado com sucesso!"
else
    print_warning "Erro ao baixar modelo. Tentando novamente..."
    sleep 10
    docker-compose exec -T ollama ollama pull llama3.2:3b
fi

# Start API service
print_status "Iniciando API service..."
docker-compose up -d app-api

# Wait for API to be ready
print_status "Aguardando API..."
sleep 20

# Initialize database
print_status "Inicializando banco de dados..."
docker-compose exec -T app-api python scripts/init_db.py

if [ $? -eq 0 ]; then
    print_success "Banco de dados inicializado com sucesso!"
else
    print_error "Erro ao inicializar banco de dados!"
fi

# Start remaining services
print_status "Iniciando serviços restantes..."
docker-compose up -d

# Wait for all services
print_status "Aguardando todos os serviços..."
sleep 15

# Health checks
print_status "Verificando saúde dos serviços..."

# Check API health
if curl -f -s http://localhost:8000/health > /dev/null; then
    print_success "✅ API está saudável!"
else
    print_warning "⚠️  API não está respondendo"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
    print_success "✅ Redis está funcionando!"
else
    print_warning "⚠️  Redis não está respondendo"
fi

# Check Ollama
if curl -f -s http://localhost:11434/api/tags > /dev/null; then
    print_success "✅ Ollama está funcionando!"
else
    print_warning "⚠️  Ollama não está respondendo"
fi

# Show service status
print_status "Status dos serviços:"
docker-compose ps

echo ""
echo "🎉 SETUP COMPLETO!"
echo "==================="
echo ""
echo "📌 Pontos de Acesso:"
echo "   🌐 API Documentation: http://localhost:8000/docs"
echo "   📊 Flower Dashboard:  http://localhost:5555 (admin/admin123)"
echo "   💾 Health Check:      http://localhost:8000/health"
echo "   🤖 Ollama API:        http://localhost:11434"
echo ""
echo "🔑 Credenciais Padrão:"
echo "   📧 Admin Email:    admin@example.com"
echo "   🔒 Admin Password: admin123"
echo "   🌸 Flower Login:   admin/admin123"
echo ""
echo "🛠️  Comandos Úteis:"
echo "   📋 Ver logs:           docker-compose logs -f"
echo "   ⏹️  Parar serviços:     docker-compose down"
echo "   🔄 Reiniciar:          docker-compose restart"
echo "   📊 Status:             docker-compose ps"
echo "   🧪 Executar testes:    python run_tests.py"
echo ""
echo "⚠️  IMPORTANTE: Altere as senhas padrão em produção!"
echo ""