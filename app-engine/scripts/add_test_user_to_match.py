#!/usr/bin/env python3
"""
Script to add test users to a match.

Usage:
    cd app-engine
    python scripts/add_test_user_to_match.py <match_id>
"""
import sys
import os

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import firebase_admin
from firebase_admin import firestore
from flask import Flask

# Initialize Firebase
firebase_admin.initialize_app()

app = Flask("add_test_user")
app.db_client = firestore.client()

# Import after setting up app context
from src.blueprints.matches import add_user_to_match


def main():
    if len(sys.argv) < 2:
        print("Error: match_id is required")
        print("Usage: python scripts/add_test_user_to_match.py <match_id>")
        sys.exit(1)
    
    match_id = sys.argv[1]
    
    # Use existing test users (test_0 through test_9)
    test_user_ids = [f"test_{i}" for i in range(10)]
    
    print(f"\n=== Adding test users to match {match_id} ===\n")
    
    with app.app_context():
        for user_id in test_user_ids:
            print(f"Adding {user_id}...")
            add_user_to_match(match_id, user_id)
        
        # Show current going list
        match_data = app.db_client.collection("matches").document(match_id).get().to_dict()
        going = match_data.get("going", {})
        print(f"\n=== Match now has {len(going)} players ===")
        for uid in going:
            user_doc = app.db_client.collection("users").document(uid).get()
            user_name = user_doc.to_dict().get("name", "Unknown") if user_doc.exists else "Unknown"
            print(f"  - {uid}: {user_name}")


if __name__ == "__main__":
    main()
