from datetime import datetime
import os, uuid, traceback
# NOTE: Assuming util, refresh_session_user, and notification_service are correctly imported/available
# If you receive errors about these, ensure they are defined or imported in your main app.py
from backend import util
from backend.notification_service import notification_service

loans_file = "data/loans.json"
# System-defined default interest rate (10% annual)
DEFAULT_SYSTEM_INTEREST_RATE = 0.10 

# -----------------------------
# Internal helper
# -----------------------------
def _list_loans():
    # Ensure loans_file exists or return an empty list if read fails gracefully
    return util.read_json(loans_file) or []

def list_loans():
    return _list_loans()

def get_user_loans(username, role):
    all_loans = _list_loans()
    if role == "borrower":
        return [l for l in all_loans if l.get("borrower_username") == username]
    elif role == "lender":
        return [l for l in all_loans if l.get("lender_username") == username]
    return []

# -----------------------------
# Add Loan Request (Borrower)
# -----------------------------
def add_loan_request(
    borrower_username,
    borrower_email,
    amount,
    duration_months,
    description=None,
    proof_of_income=None
):
    loans = _list_loans()
    loan_id = str(uuid.uuid4())

    new_loan = {
        "id": loan_id,
        "borrower_username": borrower_username,
        "lender_username": None,
        "amount": float(amount),
        "duration_months": int(duration_months),
        "status": "pending",
        "total_repayment": None,
        "description": description,
        "proof_of_income": proof_of_income,
        "created_at": datetime.utcnow().isoformat(),
        "funded_at": None,
        "approved_at": None
    }

    loans.append(new_loan)
    util.write_json(loans_file, loans)

    # Notify borrower (does not break on error)
    try:
        notification_service.notify_loan_requested(borrower_username, amount)
    except Exception as e:
        print("[loan.add_loan_request] notification error:", e)

    return new_loan

# -----------------------------
# Fund Loan 
# -----------------------------
def fund_loan(loan_id, lender_username): # Removed interest_rate argument
    loans = _list_loans()
    
    # Use the system default rate for calculation
    rate = DEFAULT_SYSTEM_INTEREST_RATE 

    for loan in loans:
        if loan.get("id") == loan_id:
            if loan.get("status") != "pending":
                # Raise a specific, informative exception
                raise Exception("Loan is not available for funding")
            
            # --- Defensive Data Retrieval and Conversion ---
            try:
                loan_amount = float(loan.get("amount", 0))
                duration_months = int(loan.get("duration_months", 0))
            except ValueError as e:
                # If conversion fails (e.g., 'amount' is "ABC")
                raise Exception(f"Loan data contains invalid numerical values: {e}")

            # --- Update Loan Fields ---
            loan["lender_username"] = lender_username
            # Set the rate used by the system
            loan["interest_rate"] = rate 
            
            # --- Calculations (using converted, safe variables) ---
            loan["interest_amount"] = util.get_interest_amount(loan_amount, rate, duration_months)
            loan["total_repayment"] = util.get_total_repayment(loan_amount, loan["interest_amount"])
            
            # --- Finalize Status and Save ---
            loan["status"] = "approved_by_lender"
            loan["funded_at"] = datetime.utcnow().isoformat()
            
            util.write_json(loans_file, loans)
            return loan
            
    # If the loop finishes without finding the loan
    raise Exception("Loan not found")

# -----------------------------
# Approve Loan (finalize)
# -----------------------------
def approve_loan(loan_id):
    loans = _list_loans()
    for loan in loans:
        if loan["id"] == loan_id:
            if loan["status"] != "approved_by_lender":
                raise Exception("Loan must be funded first")
            loan["status"] = "funded"
            loan["approved_at"] = datetime.utcnow().isoformat()
            util.write_json(loans_file, loans)
            return loan
    raise Exception("Loan not found")

# -----------------------------
# Reject Loan
# -----------------------------
def reject_loan(loan_id):
    loans = _list_loans()
    for loan in loans:
        if loan["id"] == loan_id:
            loan["status"] = "rejected"
            util.write_json(loans_file, loans)
            return loan
    raise Exception("Loan not found")