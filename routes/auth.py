# Import Flask view helpers for template rendering, form data extraction, URL redirects, sessions, and messages
from flask import render_template, request, redirect, url_for, session, flash  # Handles user input and HTTP navigation

# Import password hashing utilities to securely store and verify customer credentials (bcrypt/pbkdf2)
from werkzeug.security import generate_password_hash, check_password_hash  # Cryptographic password security

# Import token verification exceptions from itsdangerous for password reset link validation
from itsdangerous import BadSignature, SignatureExpired  # Handles invalid or expired reset tokens

# Import shared application helpers, database runners, input validators, rate limiters, and audit loggers
from extensions import (app, query, execute, reset_serializer, RESET_TOKEN_MAX_AGE,  # App, DB, and token settings
                        is_valid_email, is_valid_phone, is_valid_password,  # Validation helper functions
                        auth_is_rate_limited, record_failed_auth, clear_auth_attempts,  # Login brute-force defense
                        send_email, audit)  # Automated email dispatcher and audit logger

# Define URL route for new user account registration supporting both GET (display form) and POST (submit form)
@app.route("/register", methods=["GET", "POST"])  # Accessible at /register
def register():  # Controller function managing account registration
    error = None  # Variable to store validation error message if any occurs
    if request.method == "POST":  # Check if customer submitted the registration form
        name = request.form.get("name", "").strip()  # Retrieve and clean full name from form submission
        email = request.form.get("email", "").strip().lower()  # Retrieve and normalize email to lowercase
        phone = request.form.get("phone", "").strip()  # Retrieve and clean phone number
        password = request.form.get("password", "")  # Retrieve plaintext password input

        if not name:  # Validate that name is not blank
            error = "Please enter your full name."  # Error if name is empty
        elif not is_valid_email(email):  # Validate email format using regular expression
            error = "Please enter a valid email address."  # Error if email pattern fails
        elif not is_valid_phone(phone):  # Validate that phone number consists of exactly 10 digits
            error = "Phone number must be exactly 10 digits."  # Error if phone is not 10 digits
        elif not is_valid_password(password):  # Validate password complexity (uppercase, lowercase, number, symbol)
            error = "Password must be at least 8 characters and include uppercase, lowercase, a number, and a special character."  # Complexity error
        else:  # All client inputs are valid
            existing = query("SELECT user_id FROM users WHERE email=%s", (email,), one=True)  # Check if email is already taken
            if existing:  # If user with this email already exists
                error = "Email already registered."  # Prevent duplicate accounts
            else:  # Email is unique and inputs are valid
                execute("INSERT INTO users (full_name,email,phone,password) VALUES (%s,%s,%s,%s)",  # Insert new user record
                        (name, email, phone, generate_password_hash(password)))  # Stores securely hashed password
                flash("Account created! Please log in.", "success")  # Notify user that account was created
                return redirect(url_for("login"))  # Redirect user to login page
    return render_template("auth_form.html", auth_mode="register", error=error)  # Render registration HTML form

# Define URL route for customer login supporting GET (display form) and POST (submit credentials)
@app.route("/login", methods=["GET", "POST"])  # Accessible at /login
def login():  # Controller function managing user authentication
    error = None  # Variable to store error message
    if request.method == "POST":  # Check if user submitted login credentials
        email = request.form.get("email", "").strip().lower()  # Extract email in lowercase
        password = request.form.get("password", "")  # Extract plaintext password entered by user
        if auth_is_rate_limited(email):  # Check if IP/account has exceeded 5 failed attempts within 15 minutes
            error = "Too many failed attempts. Please wait 15 minutes and try again."  # Brute-force protection error
        else:  # Account is not rate limited
            user = query("SELECT * FROM users WHERE email=%s", (email,), one=True)  # Look up user record by email
            if user and check_password_hash(user["password"], password):  # Verify password matches stored cryptographic hash
                clear_auth_attempts(email)  # Reset failed attempt counter on successful login
                session.clear()  # Clear any existing session data
                session.permanent = True  # Enable session timeout persistence (8 hours)
                session["user_id"] = user["user_id"]  # Store authenticated user ID in secure session cookie
                session["user_name"] = user["full_name"]  # Store user name in session for header display
                return redirect(url_for("user_dashboard"))  # Redirect authenticated customer to their dashboard
            record_failed_auth(email)  # Log failed login attempt for rate limiting
            error = "Invalid email or password."  # Generic security message avoiding account enumeration
    return render_template("auth_form.html", auth_mode="login", error=error)  # Render login HTML form

# Define URL route for requesting password reset instructions
@app.route("/forgot-password", methods=["GET", "POST"])  # Accessible at /forgot-password
def forgot_password():  # Controller function handling forgot password requests
    error = None  # Holds error message
    if request.method == "POST":  # Check if user submitted forgot password form
        email = request.form.get("email", "").strip().lower()  # Extract submitted email
        user = query("SELECT user_id FROM users WHERE email=%s", (email,), one=True)  # Check if account exists
        notice = "If that email is registered, a reset link has been generated."  # Safe generic feedback
        reset_link = None  # Holds password reset URL
        if user:  # If user exists in database
            token = reset_serializer.dumps(email, salt="password-reset")  # Generate signed cryptographic token
            reset_link = url_for("reset_password", token=token, _external=True)  # Build full absolute URL
            if send_email(email, "Reset your TravelWorld password",  # Send reset link via SMTP email
                          f"Use this link within 30 minutes to reset your password:\n{reset_link}"):  # Email content
                reset_link = None  # Hide link from UI if successfully dispatched via email
                notice = "If that email is registered, a password reset link has been sent."  # Success notice
        return render_template("auth_form.html", auth_mode="forgot_password",  # Display confirmation page
                               error=error, notice=notice, reset_link=reset_link)  # Supplies reset link/notice
    return render_template("auth_form.html", auth_mode="forgot_password", error=error)  # Render initial form

# Define URL route to reset password using signed verification token
@app.route("/reset-password/<token>", methods=["GET", "POST"])  # Token passed dynamically in URL
def reset_password(token):  # Controller function handling password update via token
    try:  # Attempt to decode and verify token
        email = reset_serializer.loads(token, salt="password-reset", max_age=RESET_TOKEN_MAX_AGE)  # Validates signature and age (30m)
    except SignatureExpired:  # Raised if token timestamp is older than 30 minutes
        flash("That reset link has expired. Please request a new one.", "error")  # Alert user token expired
        return redirect(url_for("forgot_password"))  # Redirect to request new link
    except BadSignature:  # Raised if token was tampered with or corrupted
        flash("That reset link is invalid.", "error")  # Alert user token invalid
        return redirect(url_for("forgot_password"))  # Redirect to request new link

    if request.method == "POST":  # If user submitted new password
        password = request.form.get("password", "")  # Extract new password from form
        if not is_valid_password(password):  # Verify new password meets strength requirements
            flash("Password must be at least 8 characters and include uppercase, lowercase, a number, and a special character.", "error")  # Validation message
            return render_template("auth_form.html", auth_mode="new_password", email=email, token=token)  # Re-display form
        execute("UPDATE users SET password=%s, updated_at=NOW() WHERE email=%s",  # Update password in database
                (generate_password_hash(password), email))  # Securely hashes new password
        flash("Password updated! Please log in.", "success")  # Notify user of successful update
        return redirect(url_for("login"))  # Redirect to login page

    return render_template("auth_form.html", auth_mode="new_password", email=email, token=token)  # Display new password form

# Define URL route to log out of current session
@app.route("/logout")  # Accessible at /logout
def logout():  # Controller function ending session
    audit("logout")  # Record logout action in audit log table
    session.clear()  # Clear all session variables, invalidating the session cookie
    return redirect(url_for("home"))  # Redirect user back to homepage
