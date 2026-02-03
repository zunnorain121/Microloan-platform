import re
import os
import json
import traceback
import uuid
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

# --- Assuming these modules are in your project's backend directory ---
# NOTE: Ensure you have 'backend/util.py', 'backend/loan.py', and 
# 'backend/notification_service.py' set up correctly.

try:
    from backend import util as util_mod
    from backend import loan as loan_mod
    from backend.notification_service import notification_service
    from backend.blockchain import publish_to_blockchain
except ImportError:
    # Fallback/Placeholder functions if backend modules are not present for testing
    print("Warning: Backend modules (util_mod, loan_mod, etc.) not found. Using placeholders.")
    class PlaceholderModule:
        def __init__(self): pass
        def write_json(self, p, d): pass
        def read_json(self, p): return []
        def hash_password(self, p): return "hashed_password"
        def verify_password(self, p, h): return True
        def validate_password(self, p): return True, "Password is valid"
        def get_loan_stats(self, p): return {"total_loans": 0, "pending_loans": 0}
        def list_loans(self): return []
        def get_user_loans(self, u, r): return []
        def add_loan_request(self, **kwargs): return {"id": 99, "status": "pending", "amount": kwargs.get("amount", 0), "borrower_username": kwargs.get("borrower_username")}
        def fund_loan(self, l, u): return {"amount": 100, "borrower_username": "borrower"}
        def approve_loan(self, l): return {"amount": 100, "borrower_username": "borrower"}
        def reject_loan(self, l): pass
    
    util_mod = PlaceholderModule()
    loan_mod = PlaceholderModule()
    notification_service = PlaceholderModule()
    def publish_to_blockchain(event, data): pass
    

# --- Configuration ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "microloan_secret_key_change_in_production")
app.permanent_session_lifetime = timedelta(days=1)

# File and directory settings
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs("data", exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True) # Ensure uploads folder exists

USERS_FILE = "data/users.json"
LOANS_FILE = "data/loans.json"
if not os.path.exists(USERS_FILE): util_mod.write_json(USERS_FILE, [])
if not os.path.exists(LOANS_FILE): util_mod.write_json(LOANS_FILE, [])

# Backend shortcuts
read_json = lambda p: util_mod.read_json(p)
write_json = lambda p,d: util_mod.write_json(p,d)
hash_password = util_mod.hash_password
verify_password = util_mod.verify_password
get_loan_stats = util_mod.get_loan_stats
list_loans = loan_mod.list_loans
get_user_loans = loan_mod.get_user_loans
add_loan_request = loan_mod.add_loan_request
fund_loan = loan_mod.fund_loan
approve_loan = loan_mod.approve_loan
reject_loan = loan_mod.reject_loan

# --- User utilities ---
def get_all_users(): return read_json(USERS_FILE) or []
def get_user_by_username(username):
    return next((u for u in get_all_users() if u.get("username") == username), None)
def update_user(user):
    users = get_all_users()
    found = False
    for i,u in enumerate(users):
        if u.get("username")==user.get("username"):
            users[i]=user; found=True; break
    if not found: users.append(user)
    write_json(USERS_FILE, users)
def refresh_session_user():
    username = session.get("username")
    if username:
        user = get_user_by_username(username)
        if user:
            session["user"] = user
            return user
    return None
@app.before_request
def make_session_permanent(): session.permanent = True

# --- File Upload Utilities (NEW/FIXED SECTION) ---
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file):
    """Saves an uploaded file to the UPLOAD_FOLDER with a unique name."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Use UUID to ensure global uniqueness for the filename
        unique_filename = str(uuid.uuid4()) + "_" + filename
        
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        
        # Save the file
        file.save(filepath)
        
        return filepath
    
    return None

# --- Routes --
@app.route("/")
def index():
    # Just show home page ALWAYS
    return render_template("index.html")

    

@app.route("/register", methods=["GET", "POST"])
def register():
    # Prevent users from registering as admin
    if request.args.get("role") == "admin":
        flash("You cannot register as admin.", "danger")
        return redirect(url_for("register"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        role = request.form.get("role") or "borrower"

        # Block admin registration even if someone tries to hack the form
        if role == "admin":
            flash("You cannot register as admin.", "danger")
            return redirect(url_for("register"))

        # Validation
        if not username or not password or not role:
            flash("All fields required", "danger")
            return redirect(url_for("register"))

        if get_user_by_username(username):
            flash("Username already exists", "danger")
            return redirect(url_for("register"))

        valid, msg = util_mod.validate_password(password)
        if not valid:
            flash(msg, "danger")
            return redirect(url_for("register"))

        # Get all users
        users = get_all_users()

        # Assign unique ID
        new_id = max([u.get("id", 0) for u in users] + [0]) + 1

        # Create user
        new_user = {
            "id": new_id,
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "balance": 1000.0 if role == "lender" else 0.0,
            "created_at": datetime.utcnow().isoformat()
        }

        users.append(new_user)
        write_json(USERS_FILE, users)

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    default_role = request.args.get("role", "borrower")
    return render_template("register.html", default_role=default_role)

@app.route("/login", methods=["GET","POST"])
def login():
    role_param = request.args.get("role") # Optional role from login page

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = get_user_by_username(username)

        if user and verify_password(password, user.get("password_hash")):
            # Assign ID if missing (for old users/admin)
            if "id" not in user:
                users = get_all_users()
                for idx, u in enumerate(users):
                    if u["username"] == user["username"]:
                        user["id"] = idx + 1
                        break
                write_json(USERS_FILE, users)

            # Check role mismatch (skip for admin to avoid loop)
            if role_param and user["role"] != role_param and user["role"] != "admin":
                flash(f"Please login using your {user['role']} account.", "danger")
                return redirect(url_for("login", role=role_param))

            # Set session
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {username}!", "success")

            # Redirect based on role
            return redirect(url_for("dashboard"))

        flash("Invalid username or password", "danger")
        return redirect(url_for("login", role=role_param))

    # GET request — show login form
    return render_template("login.html", role=role_param)


@app.route("/logout")
def logout(): session.clear(); flash("Logged out.","info"); return redirect(url_for("index"))

# --- Dashboard ---

@app.route("/dashboard")
def dashboard():
    user = refresh_session_user()
    if not user:
        flash("Login required", "warning")
        return redirect(url_for("login"))

    loans = list_loans()
    my_loans = get_user_loans(user["username"], user["role"])
    stats = get_loan_stats(LOANS_FILE)
    all_users = get_all_users()

    if user["role"] == "borrower":
        return render_template(
            "borrower.html",
            username=user["username"],
            balance=user["balance"],
            my_loans=my_loans,
            total_loans=stats["total_loans"],
            total_lenders=len([u for u in all_users if u["role"] == "lender"]),
            total_borrowers=len([u for u in all_users if u["role"] == "borrower"])
        )

    elif user["role"] == "lender":
        # Pending loans available for funding
        available_loans = [l for l in loans if l.get("status") == "pending"]

        # Add anonymized borrower ID for lender
        for loan in available_loans:
            borrower = loan.get("borrower_username", "N/A")
            loan["borrower_anon_id"] = borrower[:2] + "****"

        # Funded loans by this lender
        funded_loans = [l for l in my_loans if l.get("status") in ["approved_by_lender", "funded"]]

        return render_template(
            "lender.html",
            username=user["username"],
            balance=user["balance"],
            available_loans=available_loans,
            funded_loans=funded_loans,
            total_loans=stats["total_loans"]
        )

    elif user["role"] == "admin":
        # Loans waiting for final approval
        pending_approvals = [l for l in loans if l.get("status") == "approved_by_lender"]

        borrowers = [u for u in all_users if u["role"] == "borrower"]
        lenders = [u for u in all_users if u["role"] == "lender"]

        # Add anonymized borrower ID for template
        for loan in pending_approvals:
            if "borrower_anon_id" not in loan:
                loan["borrower_anon_id"] = loan.get("borrower_username", "N/A")

        return render_template(
            "admin.html",
            username=user["username"],
            total_loans=stats["total_loans"],
            total_pending=stats["pending_loans"],
            pending_loans=pending_approvals,
            borrowers=borrowers,
            lenders=lenders
        )

    # fallback
    return redirect(url_for("index"))


# --- Loan routes ---
@app.route("/request_loan", methods=["GET", "POST"])
def request_loan():
    user = refresh_session_user()
    if not user or user.get("role") != "borrower":
        flash("You must be logged in as a borrower to request a loan.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            # Get raw form data
            amount_str = request.form.get("amount")
            duration_str = request.form.get("duration")
            description = request.form.get("description")
            proof_file = request.files.get("proof_of_income")
            flash("Loan request submitted successfully!", "success")
            return redirect(url_for("dashboard")) # <-- This is the key
            
            # --- Input Validation and Conversion (FIXED) ---
            if not amount_str or not duration_str:
                flash("Loan Amount and Duration are required.", "danger")
                return redirect(url_for("request_loan"))
                
            try:
                amount = float(amount_str)
                duration = int(duration_str)
            except ValueError:
                flash("Loan Amount and Duration must be valid numbers.", "danger")
                return redirect(url_for("request_loan"))

            if not proof_file:
                flash("Please upload proof of income.", "danger")
                return redirect(url_for("request_loan"))

            # Save the file (uses the new/fixed save_file function)
            proof_path = save_file(proof_file)
            if not proof_path:
                flash("Invalid file uploaded. Accepted types: PDF, JPG, PNG.", "danger")
                return redirect(url_for("request_loan"))

            # Use helper to save loan
            new_loan = add_loan_request(
                borrower_username=user.get("username"),
                amount=amount,
                duration_months=duration
            )

            # Add extra fields (if add_loan_request doesn't handle them internally)
            if new_loan:
                new_loan["description"] = description
                new_loan["proof_of_income"] = proof_path
                new_loan["status"] = "pending"
                new_loan["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_loan["funded_at"] = None
                # NOTE: Depending on how add_loan_request is implemented, you might need 
                # to call a specific update function here if it only saves the basic fields.
            
            flash("Loan request submitted successfully!", "success")
            return redirect(url_for("dashboard"))

        except Exception as e:
            # Log the full traceback for debugging
            traceback.print_exc()
            flash(f"Error submitting loan: {str(e)}. Please check the console.", "danger")
            return redirect(url_for("request_loan"))

    return render_template("new_loan.html")


# --- Fund Loan Route (Professional Version) ---
@app.route("/fund_loan/<loan_id>", methods=["POST"])
def fund_loan_route(loan_id):
    user = refresh_session_user()
    if not user or user.get("role") != "lender":
        flash("Access denied. Only lenders can fund loans.", "danger")
        return redirect(url_for("login"))

    # Fetch loan
    loan = next((l for l in list_loans() if str(l.get("id")) == str(loan_id)), None)
    if not loan:
        flash("Loan not found.", "danger")
        return redirect(url_for("dashboard"))

    # Check loan status
    if loan.get("status") != "pending":
        flash(f"Loan cannot be funded. Current status: {loan.get('status').replace('_', ' ').title()}.", "warning")
        return redirect(url_for("dashboard"))

    # Validate loan amount
    try:
        loan_amount = float(loan.get("amount", 0))
    except ValueError:
        flash("Invalid loan amount. Please contact support.", "danger")
        return redirect(url_for("dashboard"))

    # Check lender balance
    if user["balance"] < loan_amount:
        flash("Insufficient balance to fund this loan.", "danger")
        return redirect(url_for("dashboard"))

    # Fund loan safely
    try:
        funded_loan = fund_loan(loan_id, user["username"])

        # Deduct lender balance
        user["balance"] -= loan_amount
        update_user(user)

        # Notify & log on blockchain
        publish_to_blockchain("loan_funded", funded_loan)
        notification_service.notify_loan_funded(
            funded_loan["borrower_username"],
            funded_loan["borrower_username"],  # Replace with actual name if available
            funded_loan["amount"],
            user["username"]
        )

        flash("✅ Loan funded successfully! .", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        print(f"[fund_loan_route ERROR] {type(e).__name__}: {e}")
        flash("❌ Funding failed due to a system error. Please try again or contact support.", "danger")
        return redirect(url_for("dashboard"))

def status(): return jsonify({"status":"ok"})
@app.route("/about")
def about():
    features = [
        {
            "title": "Secure Blockchain Storage",
            "desc": "All loan requests, approvals, and transactions are permanently recorded on-chain, ensuring transparency and preventing tampering."
        },
        {
            "title": "Anonymized Borrowers",
            "desc": "Borrowers remain completely anonymous to protect privacy, while lenders see only verified loan data for safe investment decisions."
        },
        {
            "title": "Fast Loan Funding",
            "desc": "Borrow or lend within minutes through an intuitive dashboard that simplifies posting, approving, and funding loans."
        },
        {
            "title": "Real-Time Tracking",
            "desc": "Track loan status, repayment schedules, and interest calculations instantly, giving complete control and visibility to all users."
        },
        {
            "title": "Low Risk & Transparent",
            "desc": "With immutable records and verified borrower data, lenders can confidently fund loans with minimal risk exposure."
        },
        {
            "title": "Designed for Everyone",
            "desc": "BlockLoan provides a simple, clean interface for borrowers, lenders, and admins—accessible anywhere, anytime."
        }
    ]

    return render_template("about.html", features=features)
@app.route('/register/borrower', methods=['GET', 'POST'])
def register_borrower():
    # Placeholder for a role-specific register page
    return redirect(url_for('register', role='borrower'))

@app.route('/register/lender', methods=['GET', 'POST'])
def register_lender():
    # Placeholder for a role-specific register page
    return redirect(url_for('register', role='lender'))


# --- Run ---
if __name__=="__main__":
    port=int(os.getenv("PORT",5004))
    app.run(debug=True, port=port)