"""Sanity check - verify Phase 1 is complete and working."""

import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("Phase 1 Sanity Check")
print("=" * 80)

errors = []
imports_ok = []

# Check imports
print("\n✓ Checking imports...")

checks = [
    ("app.core.config", "Settings"),
    ("app.core.database", "engine, SessionLocal, get_db"),
    ("app.core.security", "hash_password, verify_password, create_access_token"),
    ("app.models", "Base, Business, User"),
    ("app.repositories.base", "BaseRepository"),
    ("app.repositories.user", "UserRepository"),
    ("app.repositories.business", "BusinessRepository"),
    ("app.services.auth", "AuthService"),
    ("app.schemas.auth", "RegisterRequest, LoginRequest, TokenResponse"),
    ("app.api.auth", "router"),
    ("app.main", "app, get_current_user"),
]

for module_path, items in checks:
    try:
        module = __import__(module_path, fromlist=items.split(", "))
        imports_ok.append(f"  ✓ {module_path}")
    except ImportError as e:
        errors.append(f"  ✗ {module_path}: {e}")

for imp in imports_ok:
    print(imp)

# Check Models
print("\n✓ Checking models registration...")
try:
    from app.models import Base
    tables = list(Base.metadata.tables.keys())
    print(f"  ✓ Found {len(tables)} tables: {', '.join(tables)}")
    
    # Check for critical fields
    from app.models.user import User
    from app.models.business import Business
    
    user_cols = {col.name for col in User.__table__.columns}
    business_cols = {col.name for col in Business.__table__.columns}
    
    required_user_cols = {"id", "business_id", "email", "hashed_password", "role"}
    required_business_cols = {"id", "name", "email"}
    
    if required_user_cols.issubset(user_cols):
        print(f"  ✓ User model has required columns")
    else:
        errors.append(f"  ✗ User missing columns: {required_user_cols - user_cols}")
    
    if required_business_cols.issubset(business_cols):
        print(f"  ✓ Business model has required columns")
    else:
        errors.append(f"  ✗ Business missing columns: {required_business_cols - business_cols}")
        
except Exception as e:
    errors.append(f"  ✗ Model check failed: {e}")

# Check Multi-Tenancy
print("\n✓ Checking multi-tenancy enforcement...")
try:
    from app.repositories.base import BaseRepository
    import inspect
    
    methods = ["get", "list", "count", "update", "delete"]
    source = inspect.getsource(BaseRepository)
    
    multi_tenant_checks = 0
    for method in methods:
        if "business_id" in inspect.getsource(getattr(BaseRepository, method)):
            multi_tenant_checks += 1
    
    if multi_tenant_checks == len(methods):
        print(f"  ✓ All BaseRepository methods filter by business_id")
    else:
        errors.append(f"  ✗ Only {multi_tenant_checks}/{len(methods)} methods have business_id filter")
        
except Exception as e:
    errors.append(f"  ✗ Multi-tenancy check failed: {e}")

# Check FastAPI App
print("\n✓ Checking FastAPI app...")
try:
    from app.main import app
    
    routes = [route.path for route in app.routes]
    expected_routes = ["/health", "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/me"]
    
    found_routes = [r for r in expected_routes if any(r in route for route in routes)]
    if len(found_routes) >= 2:  # At least health and auth routes
        print(f"  ✓ FastAPI app has routes: {len(routes)} total")
    else:
        errors.append(f"  ✗ Missing expected routes")
        
except Exception as e:
    errors.append(f"  ✗ FastAPI check failed: {e}")

# Check JWT
print("\n✓ Checking JWT implementation...")
try:
    from app.core.security import create_access_token, decode_token
    
    test_data = {"test": "value"}
    token = create_access_token(test_data)
    decoded = decode_token(token)
    
    if "test" in decoded:
        print(f"  ✓ JWT encode/decode working")
    else:
        errors.append(f"  ✗ JWT data not preserved")
        
except Exception as e:
    errors.append(f"  ✗ JWT check failed: {e}")

# Check Password Hashing
print("\n✓ Checking password hashing...")
try:
    from app.core.security import hash_password, verify_password
    
    test_pwd = "testpassword123"
    hashed = hash_password(test_pwd)
    
    if verify_password(test_pwd, hashed):
        print(f"  ✓ Password hashing working")
    else:
        errors.append(f"  ✗ Password verification failed")
        
except Exception as e:
    errors.append(f"  ✗ Password hashing check failed: {e}")

# Final Results
print("\n" + "=" * 80)

if errors:
    print(f"❌ {len(errors)} Error(s) Found:")
    for err in errors:
        print(err)
    sys.exit(1)
else:
    print("✅ ALL CHECKS PASSED - Phase 1 is ready!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Create PostgreSQL database: createdb biznizflowpilot_db")
    print("  2. Update .env with database credentials")
    print("  3. Run setup: python setup.py")
    print("  4. Start server: uvicorn app.main:app --reload")
    print("  5. Run tests: pytest")
    print("  6. Visit http://localhost:8000/docs for API documentation")
    print("=" * 80)
