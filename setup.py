"""Setup local development environment."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.database import init_db, engine
from app.models import Base

print("=" * 80)
print("BiznizFlowPilot - Phase 1 Setup")
print("=" * 80)

# Check environment
print("\n📋 Configuration:")
print(f"  Database: {settings.database_url}")
print(f"  Environment: {settings.environment}")
print(f"  Debug: {settings.debug}")
print(f"  Secret Key: {'SET' if settings.secret_key != 'your-super-secret-key-change-in-production' else '⚠️ DEFAULT (change in production!)'}")

# Create tables
print("\n🗄️  Creating database tables...")
try:
    init_db()
    print("  ✅ Database tables created")
except Exception as e:
    print(f"  ❌ Error creating tables: {e}")
    sys.exit(1)

# Verify models
print("\n📊 Registered models:")
for table_name, table in Base.metadata.tables.items():
    columns = [col.name for col in table.columns]
    print(f"  • {table_name}: {', '.join(columns)}")

print("\n" + "=" * 80)
print("✅ Setup complete!")
print("=" * 80)
print("\nNext steps:")
print("1. Start the server: uvicorn app.main:app --reload")
print("2. Access API docs: http://localhost:8000/docs")
print("3. Run tests: pytest")
print("=" * 80 + "\n")
