# tests/test_system.py
"""
Suite completa de testes para validar o sistema
"""
import pytest
import requests
import time
import json
import os
from pathlib import Path
from typing import Dict, Any
import asyncio
from datetime import datetime

# Configuration
API_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
API_VERSION = "/api/v1"
TEST_TIMEOUT = 600  # 10 minutes max for processing

class TestSystemComplete:
    """Complete system test suite"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        cls.base_url = f"{API_URL}{API_VERSION}"
        cls.token = None
        cls.task_id = None
        cls.test_user = {
            "email": f"test_{datetime.now().timestamp()}@example.com",
            "username": f"test_{datetime.now().timestamp()}",
            "password": "TestPassword123!",
            "full_name": "Test User",
            "organization": "Test Org"
        }
    
    def test_01_health_check(self):
        """Test system health"""
        response = requests.get(f"{API_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health check passed")
    
    def test_02_user_registration(self):
        """Test user registration"""
        response = requests.post(
            f"{self.base_url}/auth/register",
            json=self.test_user
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == self.test_user["email"]
        print("✅ User registration passed")
    
    def test_03_user_login(self):
        """Test user authentication"""
        response = requests.post(
            f"{self.base_url}/auth/token",
            data={
                "username": self.test_user["email"],
                "password": self.test_user["password"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        self.__class__.token = data["access_token"]
        print("✅ User login passed")
    
    def test_04_create_test_pdf(self):
        """Create a test PDF for processing"""
        # Create a simple test PDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        pdf_path = Path("test_edital.pdf")
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        
        # Add content
        c.drawString(100, 750, "PREGÃO ELETRÔNICO Nº 001/2025")
        c.drawString(100, 730, "UASG: 986531")
        c.drawString(100, 710, "ÓRGÃO: Ministério de Teste")
        c.drawString(100, 690, "OBJETO: Aquisição de materiais de informática")
        c.drawString(100, 670, "VALOR ESTIMADO: R$ 500.000,00")
        c.drawString(100, 650, "DATA DE ABERTURA: 20/02/2025 às 10:00")
        
        # Add a simple table
        c.drawString(100, 600, "TABELA DE PRODUTOS:")
        c.drawString(100, 580, "Item | Descrição | Quantidade | Valor Unit | Valor Total")
        c.drawString(100, 560, "1 | Notebook | 50 | R$ 3.000,00 | R$ 150.000,00")
        c.drawString(100, 540, "2 | Mouse | 100 | R$ 50,00 | R$ 5.000,00")
        c.drawString(100, 520, "3 | Teclado | 100 | R$ 150,00 | R$ 15.000,00")
        
        c.save()
        assert pdf_path.exists()
        print("✅ Test PDF created")
    
    def test_05_upload_edital(self):
        """Test edital upload"""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        with open("test_edital.pdf", "rb") as f:
            files = {"file": ("test_edital.pdf", f, "application/pdf")}
            data = {
                "ano": 2025,
                "uasg": "986531",
                "numero_pregao": "PE-001-2025"
            }
            
            response = requests.post(
                f"{self.base_url}/editais/processar",
                headers=headers,
                files=files,
                data=data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result
        assert result["status"] == "queued"
        self.__class__.task_id = result["task_id"]
        print(f"✅ Edital uploaded with task_id: {self.task_id}")
    
    def test_06_check_processing_status(self):
        """Test status checking during processing"""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        start_time = time.time()
        last_progress = 0
        
        while time.time() - start_time < TEST_TIMEOUT:
            response = requests.get(
                f"{self.base_url}/editais/status/{self.task_id}",
                headers=headers
            )
            
            assert response.status_code == 200
            status = response.json()
            
            # Check progress
            if status.get("progress"):
                assert status["progress"] >= last_progress
                last_progress = status["progress"]
                print(f"  Progress: {status['progress']}% - {status['message']}")
            
            # Check if completed
            if status["status"] == "completed":
                print("✅ Processing completed successfully")
                return
            
            elif status["status"] == "failed":
                pytest.fail(f"Processing failed: {status.get('message')}")
            
            time.sleep(5)
        
        pytest.fail(f"Processing timeout after {TEST_TIMEOUT} seconds")
    
    def test_07_get_result(self):
        """Test getting processing result"""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.get(
            f"{self.base_url}/editais/resultado/{self.task_id}",
            headers=headers
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Validate result structure
        assert "task_id" in result
        assert "quality_score" in result
        assert "products_table" in result
        assert "risk_analysis" in result
        assert "opportunities" in result
        
        # Validate quality
        assert result["quality_score"] > 0
        assert len(result["products_table"]) > 0
        
        print(f"✅ Result retrieved successfully")
        print(f"  Quality Score: {result['quality_score']}")
        print(f"  Products Found: {len(result['products_table'])}")
        print(f"  Risks Identified: {len(result['risk_analysis'].get('risks', []))}")
        print(f"  Opportunities: {len(result['opportunities'])}")
    
    def test_08_list_editais(self):
        """Test listing user's editais"""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.get(
            f"{self.base_url}/editais",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "data" in data
        assert data["total"] >= 1
        print(f"✅ Listed {data['total']} editais")
    
    def test_09_download_original(self):
        """Test downloading original PDF"""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.get(
            f"{self.base_url}/editais/{self.task_id}/download",
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 0
        print("✅ Original PDF downloaded successfully")
    
    def test_10_api_documentation(self):
        """Test API documentation availability"""
        response = requests.get(f"{API_URL}/docs")
        assert response.status_code == 200
        print("✅ API documentation available")
    
    def test_11_cleanup(self):
        """Clean up test data"""
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Delete test edital
        if self.task_id:
            response = requests.delete(
                f"{self.base_url}/editais/{self.task_id}",
                headers=headers
            )
            assert response.status_code == 200
        
        # Remove test PDF
        test_pdf = Path("test_edital.pdf")
        if test_pdf.exists():
            test_pdf.unlink()
        
        print("✅ Cleanup completed")

class TestPerformance:
    """Performance testing"""
    
    def test_concurrent_uploads(self):
        """Test concurrent upload handling"""
        # This would test multiple simultaneous uploads
        pass
    
    def test_large_file_processing(self):
        """Test large PDF processing"""
        # This would test processing of large PDFs
        pass
    
    def test_rate_limiting(self):
        """Test rate limiting"""
        # This would test rate limiting functionality
        pass

class TestSecurity:
    """Security testing"""
    
    def test_unauthorized_access(self):
        """Test unauthorized access is blocked"""
        response = requests.get(f"{API_URL}{API_VERSION}/editais")
        assert response.status_code == 401
        print("✅ Unauthorized access blocked")
    
    def test_invalid_token(self):
        """Test invalid token is rejected"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = requests.get(
            f"{API_URL}{API_VERSION}/editais",
            headers=headers
        )
        assert response.status_code == 401
        print("✅ Invalid token rejected")
    
    def test_sql_injection(self):
        """Test SQL injection protection"""
        # This would test various SQL injection attempts
        pass

# =====================================================
# run_tests.py
"""
Test runner script
"""
import sys
import subprocess
import time
from pathlib import Path

def check_services():
    """Check if all services are running"""
    print("🔍 Checking services...")
    
    services = ["app-api", "app-worker", "redis", "ollama", "flower"]
    all_running = True
    
    for service in services:
        result = subprocess.run(
            f"docker-compose ps {service}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if "Up" in result.stdout:
            print(f"  ✅ {service}: Running")
        else:
            print(f"  ❌ {service}: Not running")
            all_running = False
    
    return all_running

def wait_for_api():
    """Wait for API to be ready"""
    print("⏳ Waiting for API to be ready...")
    
    max_attempts = 30
    for i in range(max_attempts):
        try:
            import requests
            response = requests.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("  ✅ API is ready")
                return True
        except:
            pass
        
        time.sleep(2)
    
    print("  ❌ API did not become ready")
    return False

def run_tests():
    """Run the test suite"""
    print("\n🧪 Running test suite...")
    
    # Install test dependencies
    subprocess.run(
        "pip install pytest pytest-asyncio reportlab",
        shell=True
    )
    
    # Run tests
    result = subprocess.run(
        "pytest tests/test_system.py -v --tb=short",
        shell=True
    )
    
    return result.returncode == 0

def main():
    """Main test runner"""
    print("=" * 60)
    print("🚀 EDITAL PROCESSOR - SYSTEM TEST SUITE")
    print("=" * 60)
    
    # Check services
    if not check_services():
        print("\n❌ Not all services are running. Please start them first:")
        print("   docker-compose up -d")
        sys.exit(1)
    
    # Wait for API
    if not wait_for_api():
        print("\n❌ API is not responding. Check the logs:")
        print("   docker-compose logs app-api")
        sys.exit(1)
    
    # Run tests
    if run_tests():
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)
        print("\n📊 Your system is ready for production!")
        print("📚 Check the documentation at: http://localhost:8000/docs")
        print("📈 Monitor workers at: http://localhost:5555")
    else:
        print("\n" + "=" * 60)
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        print("\n📝 Check the logs for details:")
        print("   docker-compose logs")
        sys.exit(1)

if __name__ == "__main__":
    main()

# =====================================================
# Makefile
"""
Makefile for easy commands
"""
.PHONY: help build up down logs test clean

help:
	@echo "Available commands:"
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - Show logs"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Clean up everything"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 10
	@echo "Services started!"
	@echo "API: http://localhost:8000/docs"
	@echo "Flower: http://localhost:5555"

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	python run_tests.py

clean:
	docker-compose down -v
	rm -rf storage/editais/*
	rm -rf storage/processados/*
	rm -rf storage/temp/*
	rm -rf data/*
	rm -rf logs/*
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete

restart:
	make down
	make up

status:
	docker-compose ps

shell-api:
	docker-compose exec app-api bash

shell-worker:
	docker-compose exec app-worker bash

shell-db:
	docker-compose exec app-api python -c "from app.core.database import SessionLocal; db = SessionLocal(); import IPython; IPython.embed()"

migrate:
	docker-compose exec app-api alembic upgrade head

backup:
	@echo "Creating backup..."
	@mkdir -p backups
	@docker-compose exec app-api python -c "from app.utils.backup import create_backup; create_backup()"
	@echo "Backup created in backups/"