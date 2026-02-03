from backend.util import read_json, write_json, hash_password
from datetime import datetime

def reset_admin():
    users = read_json("data/users.json")

    # Remove any existing admin
    users = [u for u in users if u.get("role") != "admin"]

    # Add default admin
    users.append({
        "username": "admin",
        "password": hash_password("admin123"),  # default password
        "role": "admin",
        "balance": 10000,
        "created_at": datetime.now().isoformat()
    })

    write_json("data/users.json", users)
    print("Admin account reset!")
    print("Username: admin")
    print("Password: admin123")

if __name__ == "__main__":
    reset_admin()
