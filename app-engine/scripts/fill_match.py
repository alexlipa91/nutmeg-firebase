#!/usr/bin/env python3
"""
Script to fill a match with test users until it's full.

Usage:
    cd app-engine
    python scripts/fill_match.py <match_id>
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

app = Flask("fill_match")
app.db_client = firestore.client()

# Import after setting up app context
from src.blueprints.matches import add_user_to_match


def main():
    if len(sys.argv) < 2:
        print("Error: match_id is required")
        print("Usage: python scripts/fill_match.py <match_id>")
        sys.exit(1)
    
    match_id = sys.argv[1]
    
    # Use existing test users (test_0 through test_9)
    test_user_ids = [f"test_{i}" for i in range(10)]
    
    with app.app_context():
        # Get match data to check capacity
        match_ref = app.db_client.collection("matches").document(match_id)
        match_data = match_ref.get().to_dict()
        
        if match_data is None:
            print(f"Error: match {match_id} not found")
            sys.exit(1)
        
        max_players = match_data.get("maxPlayers", 0)
        going = match_data.get("going", {})
        current_count = len(going)
        
        print(f"\n=== Filling match {match_id} ({current_count}/{max_players} players) ===\n")
        
        if current_count >= max_players:
            print("Match is already full!")
        else:
            for user_id in test_user_ids:
                # Re-read match data to get updated count
                match_data = match_ref.get().to_dict()
                going = match_data.get("going", {})
                
                if len(going) >= max_players:
                    print("Match is now full!")
                    break
                
                if user_id in going:
                    print(f"  Skipping {user_id} (already in match)")
                    continue
                
                print(f"  Adding {user_id}...")
                add_user_to_match(match_id, user_id)
        
        # Show final state
        match_data = match_ref.get().to_dict()
        going = match_data.get("going", {})
        print(f"\n=== Match now has {len(going)}/{max_players} players ===")
        for uid in going:
            user_doc = app.db_client.collection("users").document(uid).get()
            user_name = user_doc.to_dict().get("name", "Unknown") if user_doc.exists else "Unknown"
            print(f"  - {uid}: {user_name}")


if __name__ == "__main__":
    main()
