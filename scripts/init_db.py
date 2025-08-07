#!/usr/bin/env python3
# scripts/init_db.py
"""
Database initialization script
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.core.database import SessionLocal, init_db
from app.models import User
from app.core.security import get_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_admin_user():
    """Create default admin user"""
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.email == "admin@example.com").first()
        
        if existing_admin:
            logger.info("Admin user already exists!")
            return
        
        # Create admin user
        admin_user = User(
            email="admin@example.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="System Administrator",
            organization="Internal",
            role="admin",
            is_active=True,
            is_verified=True,
            daily_quota=1000,
            created_at=datetime.utcnow()
        )
        
        db.add(admin_user)
        db.commit()
        
        logger.info("✅ Admin user created successfully!")
        logger.info("   Email: admin@example.com")
        logger.info("   Password: admin123")
        logger.info("   Role: admin")
        
    except Exception as e:
        logger.error(f"❌ Error creating admin user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """Main initialization function"""
    try:
        logger.info("🚀 Starting database initialization...")
        
        # Initialize database tables
        logger.info("📋 Creating database tables...")
        init_db()
        logger.info("✅ Database tables created successfully!")
        
        # Create admin user
        logger.info("👤 Creating admin user...")
        create_admin_user()
        
        logger.info("🎉 Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()