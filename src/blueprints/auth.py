import functools
import requests
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from ..config import FIREBASE_WEB_API_KEY

auth_bp = Blueprint('auth', __name__)

# --- Helper Decorator ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if FIREBASE_WEB_API_KEY:
            # Exchange password for auth token via Google Identity Toolkit
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
            if resp.status_code == 200:
                session.permanent = True
                session['user_id'] = resp.json()['localId']
                return redirect(url_for('main.home'))
            else:
                return render_template("auth/login.html", mode="login", error="Invalid email or password")
        else:
            return render_template("auth/login.html", mode="login", error="Authentication system not configured")
    
    return render_template("auth/login.html", mode="login")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if FIREBASE_WEB_API_KEY:
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
            if resp.status_code == 200:
                session['user_id'] = resp.json()['localId']
                flash("Registration Successful! Welcome to the Toolkit.", "success")
                return redirect(url_for('main.setup'))
            else:
                return render_template("auth/register.html", mode="register", error="Registration failed")
        else:
            return render_template("auth/register.html", mode="register", error="Registration system not configured")
    
    return render_template("auth/register.html", mode="register")

@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form.get("email")
        if FIREBASE_WEB_API_KEY:
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"
            resp = requests.post(url, json={"requestType": "PASSWORD_RESET", "email": email})
            if resp.status_code == 200:
                return render_template("auth/reset.html", mode="reset", success="Password reset email sent!")
            else:
                return render_template("auth/reset.html", mode="reset", error="Error sending reset email")
        else:
            return render_template("auth/reset.html", mode="reset", error="Password reset not configured")
    
    return render_template("auth/reset.html", mode="reset")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('auth.login'))