"""End-to-end demonstration of the lead capture and automated follow-up flow."""

import json
import requests
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_url
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.lead import Lead
from app.models.task import Task
from app.models.business import Business
from app.services.followup import FollowUpService

BASE_URL = "http://localhost:8000/api/v1"

def demo():
    print("🚀 Starting BiznizFlowPilot Feature Demo...")
    
    # 1. Register a new business
    print("\n1. Registering new business...")
    reg_data = {
        "business_name": "Demo Corp",
        "email": f"admin_{int(time.time())}@democorp.local",
        "password": "password123",
        "first_name": "Demo",
        "last_name": "Admin"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=reg_data)
    if resp.status_code != 200:
        print(f"❌ Registration failed: {resp.text}")
        return
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Registered and logged in.")

    # 2. Create a Lead
    print("\n2. Creating a new lead...")
    lead_data = {
        "source": "web_form",
        "value": "5000",
        "notes": "Interested in premium plan"
    }
    resp = requests.post(f"{BASE_URL}/leads", json=lead_data, headers=headers)
    lead = resp.json()
    lead_id = lead["id"]
    business_id = lead["business_id"]
    print(f"✅ Lead created: {lead_id} (Status: {lead['status']})")

    # 3. Simulate Idleness
    # We need to reach into the DB to backdate the lead's updated_at
    print("\n3. Simulating lead idleness (backdating 48 hours)...")
    with SessionLocal() as db:
        db_lead = db.query(Lead).filter(Lead.id == lead_id).first()
        db_lead.updated_at = datetime.now(timezone.utc) - timedelta(hours=48)
        db.commit()
    print("✅ Lead is now officially 'idle'.")

    # 4. Run Follow-Up Service
    print("\n4. Running Automated Follow-Up Service...")
    with SessionLocal() as db:
        service = FollowUpService(db)
        results = service.process_all(business_id=business_id, idle_hours=24)
        db.commit()
    print(f"✅ Follow-up processing complete: {results}")

    # 5. Verify Task Creation
    print("\n5. Verifying follow-up task creation...")
    resp = requests.get(f"{BASE_URL}/tasks", headers=headers)
    tasks = resp.json()["items"]
    
    followup_task = next((t for t in tasks if "Follow up" in t["title"]), None)
    if followup_task:
        print(f"✅ SUCCESS: Follow-up task created: '{followup_task['title']}'")
        print(f"   Priority: {followup_task['priority']}, Status: {followup_task['status']}")
    else:
        print("❌ FAILED: No follow-up task found.")

    # 6. Test Overdue Logic
    print("\n6. Testing Overdue Task logic...")
    with SessionLocal() as db:
        # Create an already overdue task
        overdue_task = Task(
            business_id=business_id,
            title="Expired Mission",
            status="pending",
            due_date=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        db.add(overdue_task)
        db.commit()
        
        service = FollowUpService(db)
        service.mark_overdue_tasks(business_id=business_id)
        db.commit()
        
        db.refresh(overdue_task)
        if overdue_task.status == "overdue":
            print(f"✅ SUCCESS: Task '{overdue_task.title}' marked as overdue.")
        else:
            print(f"❌ FAILED: Task status is {overdue_task.status}")

if __name__ == "__main__":
    demo()
