#!/bin/bash
# scripts/deploy.sh
# Production deployment script

set -e

# Configuration
ENVIRONMENT="${1:-production}"
BACKUP_BEFORE_DEPLOY="${BACKUP_BEFORE_DEPLOY:-true}"

echo "🚀 Starting deployment for $ENVIRONMENT environment..."

# Pre-deployment checks
echo "🔍 Running pre-deployment checks..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create it from .env.production template."
    exit 1
fi

# Check if required environment variables are set
required_vars=("JWT_SECRET_KEY" "FLOWER_PASSWORD")
for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env; then
        echo "❌ Required environment variable $var not set in .env"
        exit 1
    fi
done

# Backup current deployment
if [ "$BACKUP_BEFORE_DEPLOY" = "true" ]; then
    echo "💾 Creating backup before deployment..."
    if [ -f "scripts/backup.sh" ]; then
        ./scripts/backup.sh
    fi
fi

# Pull latest images (if using external registry)
echo "📦 Pulling latest images..."
docker-compose pull || true

# Build services
echo "🔨 Building services..."
docker-compose build --no-cache

# Stop services gracefully
echo "🛑 Stopping services..."
docker-compose down --timeout 30

# Start services
echo "🚀 Starting services..."
if [ "$ENVIRONMENT" = "production" ]; then
    docker-compose --profile production up -d
else
    docker-compose up -d
fi

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Run health check
echo "🏥 Running health checks..."
if [ -f "scripts/health_check.sh" ]; then
    ./scripts/health_check.sh
else
    echo "⚠️ Health check script not found, skipping..."
fi

# Initialize database if needed
echo "📋 Checking database initialization..."
if ! docker exec edital-api python -c "from app.core.database import SessionLocal; from app.models import User; db = SessionLocal(); users = db.query(User).count(); db.close(); print(f'Users: {users}')" 2>/dev/null | grep -q "Users: [1-9]"; then
    echo "🔧 Initializing database..."
    docker exec edital-api python scripts/init_db.py
fi

# Show deployment status
echo "📊 Deployment Status:"
docker-compose ps

# Show useful URLs
echo ""
echo "🌐 Service URLs:"
echo "  API Documentation: http://localhost:8001/docs"
echo "  Flower Monitoring: http://localhost:5555"
echo "  Ollama API: http://localhost:11434"

if [ "$ENVIRONMENT" = "production" ]; then
    echo "  HTTPS Site: https://your-domain.com"
fi

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "  1. Test the API endpoints"
echo "  2. Monitor logs: docker-compose logs -f"
echo "  3. Set up SSL certificates (for production)"
echo "  4. Configure monitoring and alerts"
echo "  5. Set up automated backups (cron job)"

# Show sample cron jobs
echo ""
echo "📅 Sample cron jobs for production:"
echo "# Daily backup at 2 AM"
echo "0 2 * * * /path/to/your/project/scripts/backup.sh"
echo ""
echo "# Health check every 5 minutes"
echo "*/5 * * * * /path/to/your/project/scripts/health_check.sh"