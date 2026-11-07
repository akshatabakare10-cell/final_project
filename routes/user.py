# Import Flask template rendering, form handling, redirects, sessions, and flash alerts
from flask import render_template, request, redirect, url_for, session, flash  # Manages customer web views and responses

# Import cryptographic password hashing utilities for customer profile password changes
from werkzeug.security import generate_password_hash, check_password_hash  # Safely hashes new user passwords

# Import application helpers, database runners, login decorator, image uploader, validators, and notification tools
from extensions import (app, query, execute, login_required, save_uploaded_image,  # App instance, SQL helpers, auth guard, file uploader
                        is_valid_phone, is_valid_password, audit, notify_user)  # Input format validators, audit logger, and notifier

# Define user profile route supporting GET (view profile) and POST (save profile updates)
@app.route("/profile", methods=["GET", "POST"])  # Accessible at /profile
@login_required  # Restricts route to logged-in users only
def profile():  # Controller function managing profile view and update
    uid = session["user_id"]  # Retrieves logged-in user's ID from session
    user = query("SELECT * FROM users WHERE user_id=%s", (uid,), one=True)  # Fetches current user profile from database

    if request.method == "POST":  # Check if user submitted profile edits
        name = request.form.get("full_name", "").strip()  # Extracts updated name
        phone = request.form.get("phone", "").strip()  # Extracts updated phone number
        password = request.form.get("new_password", "")  # Extracts optional new password

        if not name or not is_valid_phone(phone) or (password and not is_valid_password(password)):  # Validates all input constraints
            flash("Enter a valid name, 10-digit phone number, and a password with 8+ characters including uppercase, lowercase, a number, and a special character when changing it.", "error")  # Error message
        else:  # All fields valid
            avatar = save_uploaded_image(request.files.get("avatar"), "avatar") or user.get("avatar_filename")  # Uploads new avatar or retains current
            execute("UPDATE users SET full_name=%s,phone=%s,avatar_filename=%s,password=COALESCE(%s,password),updated_at=NOW() WHERE user_id=%s",  # Updates user profile
                    (name, phone, avatar, generate_password_hash(password) if password else None, uid))  # Updates password only if provided
            session["user_name"] = name  # Updates name in session for navbar display
            audit("profile_updated", "user", uid)  # Logs profile update in audit trail
            flash("Profile updated.", "success")  # Informs user of success
            return redirect(url_for("profile"))  # Reloads profile page with fresh data

    return render_template("profile.html", user=user)  # Renders profile page with user details

# Define route to view customer's saved wishlist packages
@app.route("/wishlist")  # Accessible at /wishlist
@login_required  # Requires customer authentication
def wishlist():  # Controller function displaying wishlist items
    rows = query("""SELECT p.* FROM wishlists w JOIN packages p ON p.package_id=w.package_id
                    WHERE w.user_id=%s ORDER BY w.created_at DESC""", (session["user_id"],))  # Joins wishlists and packages tables
    return render_template("wishlist.html", packages=rows, user_name=session.get("user_name", ""))  # Renders wishlist view

# Define route to add or remove a package from user's wishlist
@app.route("/wishlist/<int:package_id>", methods=["POST"])  # Dynamic POST endpoint with package ID
@login_required  # Requires login
def toggle_wishlist(package_id):  # Controller function toggling wishlist status
    uid = session["user_id"]  # Logged-in user ID
    existing = query("SELECT wishlist_id FROM wishlists WHERE user_id=%s AND package_id=%s",  # Check if already favorited
                     (uid, package_id), one=True)  # Query single record
    if existing:  # If already in wishlist
        execute("DELETE FROM wishlists WHERE wishlist_id=%s", (existing["wishlist_id"],))  # Remove package from wishlist
    else:  # If not yet favorited
        execute("INSERT INTO wishlists (user_id,package_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",  # Add package to wishlist
                (uid, package_id))  # Inserts record safely
    return redirect(request.referrer or url_for("wishlist"))  # Redirects back to previous page or wishlist

# Define customer main dashboard route supporting both /dashboard and /user-dashboard URLs
@app.route("/dashboard")  # Primary URL path
@app.route("/user-dashboard", endpoint="dashboard")  # Alternate endpoint alias
@login_required  # Enforces authentication
def user_dashboard():  # Controller aggregating customer dashboard metrics and data
    uid = session["user_id"]  # Current user's unique ID
    user = query("SELECT * FROM users WHERE user_id=%s", (uid,), one=True)  # Fetch user profile record
    bookings = query("""
        SELECT b.*, p.package_name, p.destination_name
        FROM bookings b JOIN packages p ON b.package_id=p.package_id
        WHERE b.user_id=%s ORDER BY b.booking_date DESC
    """, (uid,))  # Retrieve user bookings joined with package names
    payments = query("SELECT * FROM payments WHERE user_id=%s ORDER BY payment_date DESC", (uid,))  # Fetch user payments
    reports = query("SELECT * FROM user_reports WHERE user_id=%s ORDER BY created_at DESC", (uid,))  # Fetch support tickets
    notifications = query("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (uid,))  # Fetch recent alerts
    saved_plans = query("SELECT * FROM trip_plans WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (uid,))  # Fetch custom itineraries
    wishlist = query("SELECT p.* FROM wishlists w JOIN packages p ON p.package_id=w.package_id WHERE w.user_id=%s", (uid,))  # Fetch wishlist
    return render_template("dashboard.html", user=user, bookings=bookings,  # Render customer dashboard with all user records
                           payments=payments, reports=reports, notifications=notifications,  # Pass payments, tickets, and notifications
                           saved_plans=saved_plans, wishlist=wishlist)  # Pass trip planner saves and favorites

# Define route to cancel an active booking
@app.route("/bookings/<int:booking_id>/cancel", methods=["POST"])  # Dynamic POST route with booking ID
@login_required  # Requires customer authentication
def cancel_booking(booking_id):  # Controller handling booking cancellation
    uid = session["user_id"]  # Current customer ID
    booking = query("""SELECT b.*, u.email, p.package_name FROM bookings b
                       JOIN users u ON u.user_id=b.user_id
                       JOIN packages p ON p.package_id=b.package_id
                       WHERE b.booking_id=%s AND b.user_id=%s""", (booking_id, uid), one=True)  # Validates ownership and status
    if not booking or booking["status"] not in {"Pending", "Approved"}:  # Only pending or approved bookings can be cancelled
        flash("This booking can no longer be cancelled.", "error")  # Rejects invalid cancellation
        return redirect(url_for("user_dashboard"))  # Redirect to dashboard
    reason = request.form.get("reason", "Cancelled by traveler").strip()[:500]  # Extracts cancellation reason with 500-character cap
    execute("""UPDATE bookings SET status='Cancelled', cancelled_at=NOW(), cancellation_reason=%s
               WHERE booking_id=%s""", (reason or "Cancelled by traveler", booking_id))  # Updates booking status in database
    notify_user(uid, booking["email"], "Booking cancelled",  # Dispatches email and in-app cancellation notification
                f"Your booking for {booking['package_name']} has been cancelled.")  # Email message body
    flash("Your booking has been cancelled.", "success")  # Alert user that cancellation completed
    return redirect(url_for("user_dashboard"))  # Redirect back to dashboard

# Define customer support ticket submission route
@app.route("/report-issue", methods=["GET", "POST"])  # Accessible at /report-issue
@login_required  # Requires user login
def report_issue():  # Controller function managing issue reports
    if request.method == "POST":  # Check if issue form was submitted
        uid = session["user_id"]  # User ID
        service = request.form.get("service_type")  # Type of issue (Hotel, Transport, Package, Payment)
        ref_id = request.form.get("reference_id") or None  # Optional booking or package reference ID
        subject = request.form.get("subject")  # Short subject line describing the problem
        message = request.form.get("message")  # Detailed complaint explanation
        execute("INSERT INTO user_reports (user_id,service_type,reference_id,subject,message) VALUES (%s,%s,%s,%s,%s)",  # Record support ticket
                (uid, service, ref_id, subject, message))  # Saves in user_reports table
        flash("Report submitted successfully!", "success")  # Feedback to user
        return redirect(url_for("report_issue"))  # Refresh page to show submitted ticket
    reports = query("SELECT * FROM user_reports WHERE user_id=%s ORDER BY created_at DESC", (session["user_id"],))  # Fetch past tickets
    return render_template("report_issue.html", reports=reports)  # Render support page with report history
