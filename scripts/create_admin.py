# -*- coding: utf-8 -*-
"""
Created on Sat Nov 29 20:50:02 2025

@author: Administrator
"""

# scripts/create_admin.py
import os, getpass, json
from backend import util

USERS_FILE = "data/users.json"
os.makedirs("data", exist_ok=True)

def load_users():
    try:
        return util.read_json(USERS_FILE) or []
    except:
        return []

def save_users(users):
    return util.write_json(USERS_FILE, users)

def main():
    print("Create or reset admin user.")
    username = input("Admin username [admin]: ").strip() or "admin"
    pwd = getpass.getpass("Password (min 8 chars, must contain uppercase and digit): ")
    valid, msg = util.validate_password(pwd)
    if not valid:
        print("Password invalid:", msg); return
    users = load_users()
    existing = next((u for u in users if u.get("username") == username), None)
    if existing:
        existing["password_hash"] = util.hash_password(pwd)
        existing["role"] = "admin"
        print(f"Reset password for existing user {username}.")
    else:
        new_user = {
            "username": username,
            "password_hash": util.hash_password(pwd),
            "role": "admin",
            "balance": 0.0,
            "created_at": ""
        }
        users.append(new_user)
        print(f"Created admin user {username}.")
    save_users(users)
    print("Done. You can now log in with that admin account.")

if __name__ == "__main__":
    main()
