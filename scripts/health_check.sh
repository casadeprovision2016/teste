#!/bin/bash
# scripts/health_check.sh
# Production health check and monitoring script

set -e

# Configuration
LOG_FILE="./logs/health.log"
API_URL="http://localhost:8001"
FLOWER_URL="http://localhost:5555"
OLLAMA_URL="http://localhost:11434"

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Function to check service health
check_service() {
    local name="$1"
    local url="$2"
    local timeout="${3:-5}"
    
    if curl -f -s --max-time "$timeout" "$url" > /dev/null 2>&1; then
        log "✅ $name is healthy"
        return 0
    else
        log "❌ $name is unhealthy"
        return 1
    fi
}

# Function to check Docker container
check_container() {
    local container="$1"
    
    if docker inspect "$container" | grep '"Status": "running"' > /dev/null; then
        log "✅ Container $container is running"
        return 0
    else
        log "❌ Container $container is not running"
        return 1
    fi
}

log "🚀 Starting health check..."

# Check Docker containers
containers=("edital-api" "edital-worker" "edital-redis" "edital-ollama" "edital-flower")
container_failures=0

for container in "${containers[@]}"; do
    if ! check_container "$container"; then
        ((container_failures++))
    fi
done

# Check service endpoints
service_failures=0

# API Health
if ! check_service "FastAPI" "$API_URL/health" 10; then
    ((service_failures++))
fi

# Flower Dashboard
if ! check_service "Flower" "$FLOWER_URL" 5; then
    ((service_failures++))
fi

# Ollama API
if ! check_service "Ollama" "$OLLAMA_URL/api/version" 5; then
    ((service_failures++))
fi

# Check database
if docker exec edital-api python -c "from app.core.database import SessionLocal; db = SessionLocal(); db.close(); print('DB OK')" 2>&1 | grep -q "DB OK"; then
    log "✅ Database is accessible"
else
    log "❌ Database connection failed"
    ((service_failures++))
fi

# Check disk space
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    log "⚠️ Disk usage is high: ${DISK_USAGE}%"
else
    log "✅ Disk usage is normal: ${DISK_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')
log "📊 Memory usage: ${MEMORY_USAGE}%"

# Summary
total_failures=$((container_failures + service_failures))
if [ "$total_failures" -eq 0 ]; then
    log "🎉 All systems healthy!"
    exit 0
else
    log "❌ Health check failed: $total_failures issues found"
    
    # Optional: Send alert (uncomment and configure as needed)
    # curl -X POST "https://your-alert-webhook-url" -H "Content-Type: application/json" \
    #   -d "{\"text\": \"🚨 Edital Processor health check failed: $total_failures issues\"}"
    
    exit 1
fi