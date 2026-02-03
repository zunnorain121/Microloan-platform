"""
Utility functions for BlockLoan platform — safe IO, hashing, validation, and calculations.
"""
import json, os, hashlib, re, traceback
from datetime import datetime, timedelta
def read_json(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[read_json] error reading {filepath}: {e}")
    return []

def write_json(filepath, data):
    try:
        dirpath = os.path.dirname(filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[write_json] error writing {filepath}: {e}")
    return False

# Consistent hashing (use same salt across project)
_SALT = os.getenv("PASSWORD_SALT", "microloan_salt_v1_secure")

def hash_password(password: str) -> str:
    if password is None:
        password = ""
    return hashlib.sha256(( _SALT + str(password) ).encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == (hashed or "")

def generate_anon_id(username: str) -> str:
    return hashlib.sha1((str(username) + "anon").encode()).hexdigest()[:8]

def safe_float(value):
    try:
        return float(value)
    except:
        return 0.0

# Interest calculations
def get_interest_amount(principal, interest_rate, duration_months):
    """Simple interest: P * R * T / (100 * 12) where R is annual percent."""
    try:
        return round((float(principal) * float(interest_rate) * int(duration_months)) / (100 * 12), 2)
    except:
        return 0.0

def get_total_repayment(principal, interest_amount):
    try:
        return round(float(principal) + float(interest_amount), 2)
    except:
        return float(principal)

def calculate_monthly_payment(principal, interest_rate, duration_months):
    interest_amount = get_interest_amount(principal, interest_rate, duration_months)
    total_amount = get_total_repayment(principal, interest_amount)
    if duration_months == 0:
        return total_amount
    return round(total_amount / duration_months, 2)

# Dates & formatting
def format_date(date_obj):
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj)
        except:
            return str(date_obj)
    return date_obj.strftime("%B %d, %Y")

def get_loan_age_days(created_at):
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    return (datetime.utcnow() - created_at).days

def is_loan_overdue(funded_at, duration_months):
    if not funded_at:
        return False
    if isinstance(funded_at, str):
        funded_at = datetime.fromisoformat(funded_at)
    due_date = funded_at + timedelta(days=30*duration_months)
    return datetime.utcnow() > due_date

# Validation helpers
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(char.isupper() for char in password):
        return False, "Password must contain uppercase letter"
    if not any(char.isdigit() for char in password):
        return False, "Password must contain digit"
    return True, "Password is valid"

# Stats (reads loans file path if provided)
def get_loan_stats(loans_file="data/loans.json"):
    loans = read_json(loans_file) or []
    total_loans = len(loans)
    pending_loans = len([l for l in loans if l.get("status") == "pending"])
    funded = len([l for l in loans if l.get("status") == "funded"])
    return {"total_loans": total_loans, "pending_loans": pending_loans, "funded": funded}

from flask import session
USERS_FILE = "data/users.json"

def get_all_users():
    """Return all users as a list of dicts."""
    users = read_json(USERS_FILE)
    if users and isinstance(users, list) and isinstance(users[0], dict):
        return users
    return []

def refresh_session_user():
    """Return the current logged-in user object from session, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    users = get_all_users()
    user = next((u for u in users if u.get("id") == user_id), None)
    return user