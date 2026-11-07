# Import Flask view tools for template rendering, form request parsing, HTTP redirects, sessions, and notifications
from flask import render_template, request, redirect, url_for, session, flash  # Essential web controller functions

# Import password hashing utilities to verify and securely upgrade administrator credentials
from werkzeug.security import generate_password_hash, check_password_hash  # Password encryption and validation

# Import application helpers, database runners, admin decorator, image uploader, rate limiters, and notifier
from extensions import (app, query, execute, get_db, admin_required, save_uploaded_image,  # App, SQL, auth, and uploads
                        auth_is_rate_limited, record_failed_auth, clear_auth_attempts, notify_user)  # Brute-force defense and user alert

# Define administrator login route supporting GET (display form) and POST (process credentials)
@app.route("/admin/login", methods=["GET", "POST"])  # Accessible at /admin/login
def admin_login():  # Controller function handling administrative login
    error = None  # Holds error message
    if request.method == "POST":  # Check if admin submitted login form
        email = request.form.get("email", "").strip().lower()  # Normalize admin email to lowercase
        password = request.form.get("password", "")  # Extract entered password
        if auth_is_rate_limited(email):  # Check if admin account/IP exceeded failed attempt limit
            return render_template("adminlogin.html",  # Render login page with rate limit warning
                                   error="Too many failed attempts. Please wait 15 minutes and try again.")  # Rate limit message
        admin = query("SELECT * FROM admins WHERE email=%s", (email,), one=True)  # Query admin record by email
        password_matches = False  # Track password match state
        if admin:  # If an administrator record was found
            password_matches = check_password_hash(admin["password"], password)  # Check hash match
            if not password_matches and admin["password"] == password:  # Auto-upgrade plaintext legacy password if found
                execute("UPDATE admins SET password=%s WHERE admin_id=%s",  # Upgrade password to secure hash
                        (generate_password_hash(password), admin["admin_id"]))  # Hashes password
                password_matches = True  # Mark authenticated
        if password_matches:  # If password successfully matched
            clear_auth_attempts(email)  # Reset failed login count
            session.clear()  # Clear any user or guest session
            session.permanent = True  # Keep session active
            session["admin_id"] = admin["admin_id"]  # Store admin ID in session
            session["admin_name"] = admin["full_name"]  # Store admin full name in session
            return redirect(url_for("admin_dashboard"))  # Redirect to admin control panel
        record_failed_auth(email)  # Log failed attempt for rate limiting
        error = "Invalid admin credentials."  # Show error message
    return render_template("adminlogin.html", error=error)  # Render admin login template

# Define main administrator dashboard displaying analytics, revenue, recent bookings, and charts
@app.route("/admin")  # Accessible at /admin
@admin_required  # Requires administrator authentication
def admin_dashboard():  # Controller function aggregating portal statistics
    stats = query("""
        SELECT
          (SELECT COUNT(*) FROM users) AS total_users,
          (SELECT COUNT(*) FROM bookings) AS total_bookings,
          (SELECT COUNT(*) FROM packages) AS total_packages,
          (SELECT COUNT(*) FROM trip_plans) AS total_trip_plans,
          (SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='Paid') AS total_revenue
    """, one=True)  # Gathers count of users, bookings, packages, plans, and total revenue collected

    bookings = query("""
        SELECT b.*, u.full_name, p.package_name FROM bookings b
        JOIN users u ON b.user_id=u.user_id JOIN packages p ON b.package_id=p.package_id
        ORDER BY b.booking_date DESC LIMIT 8
    """)  # Fetches 8 most recent customer bookings with user and package names
    payments = query("""
        SELECT p.*, u.full_name FROM payments p
        LEFT JOIN users u ON p.user_id=u.user_id
        ORDER BY p.payment_date DESC LIMIT 6
    """)  # Fetches 6 most recent transactions
    reports = query("""
        SELECT r.*, u.full_name FROM user_reports r
        JOIN users u ON r.user_id=u.user_id
        ORDER BY r.created_at DESC LIMIT 6
    """)  # Fetches 6 most recent user support tickets
    monthly = query("""
        SELECT to_char(date_trunc('month', payment_date), 'Mon YYYY') AS month_label,
               date_trunc('month', payment_date) AS month_start,
               SUM(amount) AS revenue
        FROM payments
        WHERE status='Paid' AND payment_date >= NOW() - INTERVAL '6 months'
        GROUP BY month_start, month_label
        ORDER BY month_start
    """)  # Groups paid revenue by month over the past 6 months for chart visualization
    chart_labels = [row["month_label"] for row in monthly]  # Extracts month strings for chart X-axis
    chart_values = [float(row["revenue"] or 0) for row in monthly]  # Extracts revenue numbers for chart Y-axis

    return render_template("adminpage.html", stats=stats, bookings=bookings,  # Renders dashboard template
                           payments=payments, reports=reports,  # Supplies transaction and issue data
                           chart_labels=chart_labels, chart_values=chart_values,  # Supplies analytics data
                           admin_name=session.get("admin_name", "Admin"))  # Supplies admin name for greeting


# Define route to view and manage registered customer user accounts
@app.route("/admin/users")  # Accessible at /admin/users
@admin_required  # Requires admin access
def manage_users():  # Controller function listing all registered users
    users = query("SELECT * FROM users ORDER BY created_at DESC")  # Fetches all users newest first
    return render_template("admin_list.html", page_type="users", users=users, page_title="Manage Users")  # Renders list view

# Define route to view and manage all travel packages
@app.route("/admin/packages")  # Accessible at /admin/packages
@admin_required  # Requires admin access
def manage_packages():  # Controller function listing all packages
    packages = query("SELECT * FROM packages ORDER BY created_at DESC")  # Fetches all packages newest first
    return render_template("admin_list.html", page_type="packages", packages=packages, page_title="Manage Packages")  # Renders packages list

# Define route to create a new travel package with associated hotel and transport
@app.route("/admin/packages/add", methods=["GET", "POST"])  # Accessible at /admin/packages/add
@admin_required  # Requires admin login
def add_package():  # Controller function for adding new travel package
    if request.method == "POST":  # Admin submitted package creation form
        f = request.form  # Form dictionary
        hotel_id = None  # Holds hotel ID
        if f.get("package_hotel_name"):  # If hotel details were provided
            with get_db() as conn:  # Open database connection
                cur = conn.cursor()  # Get cursor
                cur.execute("""INSERT INTO hotels (hotel_name,destination_name,room_type,price_per_night,rating,availability)
                               VALUES (%s,%s,%s,%s,%s,%s) RETURNING hotel_id""",  # Insert hotel and return generated ID
                            (f["package_hotel_name"], f["destination"], f["package_room_type"],  # Hotel values
                             f["package_price_per_night"], f.get("package_rating") or None, f["package_availability"]))  # Hotel values
                hotel_id = cur.fetchone()[0]  # Store new hotel ID

        transport_id = None  # Holds transport ID
        if f.get("package_transport_mode"):  # If transport details were provided
            with get_db() as conn:  # Open database connection
                cur = conn.cursor()  # Get cursor
                cur.execute("""INSERT INTO transport (mode,transport_type,vehicle_name,source_name,airport_name,price)
                               VALUES (%s,%s,%s,%s,%s,%s) RETURNING transport_id""",  # Insert transport and return generated ID
                            (f["package_transport_mode"], f["package_transport_type"], f["package_vehicle_name"],  # Transport values
                             f["package_source_name"], f.get("package_airport_name", ""), f["package_transport_price"]))  # Transport values
                transport_id = cur.fetchone()[0]  # Store new transport ID

        image_path = save_uploaded_image(request.files.get("image"), "package")  # Save uploaded package hero image
        execute("""INSERT INTO packages (package_name,destination_name,description,duration,
                   travelers_limit,start_date,price,hotel_id,transport_id,image_filename)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",  # Insert package record into PostgreSQL
                (f["package_name"], f["destination"], f["description"], f["duration"],  # Package details
                 f.get("travelers_limit", 4), f.get("start_date") or None, f["price"],  # Limits and pricing
                 hotel_id, transport_id, image_path))  # Linked foreign keys and image path
        flash("Package added!", "success")  # Feedback to admin
        return redirect(url_for("manage_packages"))  # Redirect to packages table

    return render_template("admin_entity_form.html", entity_type="package",  # Render package creation form
                           package=None, package_hotel=None, package_transport=None,  # Empty initial state
                           page_title="Add Package", back_url=url_for("manage_packages"),  # Navigation links
                           back_label="Back to Packages")  # Back button text

# Define route to edit an existing package
@app.route("/admin/packages/edit/<int:package_id>", methods=["GET", "POST"])  # Dynamic route with package ID
@admin_required  # Requires admin access
def edit_package(package_id):  # Controller function editing package
    package = query("SELECT * FROM packages WHERE package_id=%s", (package_id,), one=True)  # Fetch package
    package_hotel = query("SELECT * FROM hotels WHERE hotel_id=%s", (package["hotel_id"],), one=True) if package["hotel_id"] else None  # Fetch hotel
    package_transport = query("SELECT * FROM transport WHERE transport_id=%s", (package["transport_id"],), one=True) if package["transport_id"] else None  # Fetch transport

    if request.method == "POST":  # Admin submitted edits
        f = request.form  # Form data
        image_path = save_uploaded_image(request.files.get("image"), "package")  # Save new image if uploaded
        if image_path is None:  # If no new file uploaded
            image_path = package["image_filename"]  # Preserve existing image
        execute("""UPDATE packages SET package_name=%s,destination_name=%s,description=%s,
                   duration=%s,travelers_limit=%s,start_date=%s,price=%s,image_filename=%s WHERE package_id=%s""",  # Update package table
                (f["package_name"], f["destination"], f["description"], f["duration"],  # Updated fields
                 f.get("travelers_limit", 4), f.get("start_date") or None, f["price"], image_path, package_id))  # Bound values
        flash("Package updated!", "success")  # Feedback to admin
        return redirect(url_for("manage_packages"))  # Redirect back to packages list

    return render_template("admin_entity_form.html", entity_type="package",  # Render edit form
                           package=package, package_hotel=package_hotel, package_transport=package_transport,  # Populated values
                           page_title=f"Edit — {package['package_name']}",  # Dynamic title
                           back_url=url_for("manage_packages"), back_label="Back to Packages")  # Navigation

# Define route to delete a package and its associated records
@app.route("/admin/packages/delete", methods=["POST"])  # Accessible via POST
@admin_required  # Requires admin access
def delete_package():  # Controller function deleting package
    package_id = request.form["id"]  # Package ID to delete
    execute("DELETE FROM payments WHERE booking_id IN (SELECT booking_id FROM bookings WHERE package_id=%s)", (package_id,))  # Clean payments
    execute("DELETE FROM hotel_bookings WHERE booking_id IN (SELECT booking_id FROM bookings WHERE package_id=%s)", (package_id,))  # Clean hotel bookings
    execute("DELETE FROM transport_bookings WHERE booking_id IN (SELECT booking_id FROM bookings WHERE package_id=%s)", (package_id,))  # Clean transport bookings
    execute("DELETE FROM bookings WHERE package_id=%s", (package_id,))  # Clean bookings
    execute("DELETE FROM packages WHERE package_id=%s", (package_id,))  # Delete package
    flash("Package deleted.", "success")  # Feedback to admin
    return redirect(url_for("manage_packages"))  # Redirect to list

# Define route to view, search, and paginate all customer bookings
@app.route("/admin/bookings")  # Accessible at /admin/bookings
@admin_required  # Requires admin access
def manage_bookings():  # Controller function managing booking records
    search = request.args.get("q", "").strip()  # Customer or package search query
    status = request.args.get("status", "").strip()  # Status filter (Pending, Approved, Completed, Cancelled)
    try:  # Parse page number
        page = max(1, int(request.args.get("page", 1)))  # Current pagination page number
    except ValueError:  # Fallback on invalid input
        page = 1  # Default to page 1
    per_page = 10  # Number of bookings per page

    filters, params = [], []  # Dynamic filter conditions and parameter bindings
    if search:  # If search query supplied
        filters.append("(LOWER(u.full_name) LIKE LOWER(%s) OR LOWER(p.package_name) LIKE LOWER(%s))")  # Match user or package
        params.extend([f"%{search}%", f"%{search}%"])  # Bind search parameter
    if status in {"Pending", "Approved", "Completed", "Cancelled"}:  # If valid status filter selected
        filters.append("b.status=%s")  # Filter by status column
        params.append(status)  # Bind status value

    where = f" WHERE {' AND '.join(filters)}" if filters else ""  # Construct SQL WHERE clause
    total = query(f"""SELECT COUNT(*) AS count FROM bookings b JOIN users u ON b.user_id=u.user_id
                       JOIN packages p ON b.package_id=p.package_id{where}""", params, one=True)["count"]  # Count total matching rows
    bookings = query(f"""
        SELECT b.*, u.full_name, p.package_name FROM bookings b
        JOIN users u ON b.user_id=u.user_id JOIN packages p ON b.package_id=p.package_id
        {where} ORDER BY b.booking_date DESC LIMIT %s OFFSET %s
    """, params + [per_page, (page - 1) * per_page])  # Paginated SQL query

    return render_template("admin_list.html", page_type="bookings", bookings=bookings,  # Render bookings table view
                           page_title="Manage Bookings", search=search, selected_status=status,  # Filters
                           pagination={"page": page, "pages": max(1, (total + per_page - 1) // per_page), "total": total})  # Pagination metadata

# Define route to approve a pending booking and decrement seats
@app.route("/admin/bookings/approve", methods=["POST"])  # Accessible via POST
@admin_required  # Requires admin access
def approve_booking():  # Controller function approving booking
    booking = query("""SELECT b.user_id, b.travelers, u.email, p.package_name, p.package_id, p.seats_available FROM bookings b
                       JOIN users u ON u.user_id=b.user_id JOIN packages p ON p.package_id=b.package_id
                       WHERE b.booking_id=%s AND b.status='Pending'""", (request.form["id"],), one=True)  # Retrieve booking
    if not booking:  # If booking not found or not pending
        flash("Only pending bookings can be approved.", "error")  # Error message
        return redirect(url_for("manage_bookings"))  # Return to bookings list
    if booking["seats_available"] is not None and booking["seats_available"] < booking["travelers"]:  # Check seat availability
        flash("This package no longer has enough seats.", "error")  # Not enough seats left
        return redirect(url_for("manage_bookings"))  # Return to bookings list
    execute("UPDATE packages SET seats_available=seats_available-%s WHERE package_id=%s",  # Deduct booked seats from package
            (booking["travelers"], booking["package_id"]))  # Safe seat decrement
    execute("UPDATE bookings SET status='Approved' WHERE booking_id=%s", (request.form["id"],))  # Mark booking status as Approved
    notify_user(booking["user_id"], booking["email"], "Booking approved",  # Send approval email and app alert
                f"Your booking for {booking['package_name']} has been approved.")  # Alert message
    flash("Booking approved!", "success")  # Feedback
    return redirect(url_for("manage_bookings"))  # Return to bookings list

# Define route to reject and cancel a pending booking
@app.route("/admin/bookings/reject", methods=["POST"])  # Accessible via POST
@admin_required  # Requires admin access
def reject_booking():  # Controller function rejecting booking
    booking = query("""SELECT b.user_id, u.email, p.package_name FROM bookings b
                       JOIN users u ON u.user_id=b.user_id JOIN packages p ON p.package_id=b.package_id
                       WHERE b.booking_id=%s AND b.status='Pending'""", (request.form["id"],), one=True)  # Fetch booking
    if not booking:  # Validate booking is pending
        flash("Only pending bookings can be rejected.", "error")  # Rejection error
        return redirect(url_for("manage_bookings"))  # Return to bookings list
    execute("""UPDATE bookings SET status='Cancelled', cancelled_at=NOW(),
               cancellation_reason='Cancelled by administrator' WHERE booking_id=%s""", (request.form["id"],))  # Mark Cancelled in DB
    notify_user(booking["user_id"], booking["email"], "Booking cancelled",  # Send cancellation notification
                f"Your booking for {booking['package_name']} was cancelled by the administrator.")  # Notification body
    flash("Booking rejected.", "success")  # Feedback
    return redirect(url_for("manage_bookings"))  # Return to list

# Define route to manually mark an approved trip as completed
@app.route("/admin/bookings/complete", methods=["POST"])  # Accessible via POST
@admin_required  # Requires admin access
def complete_booking():  # Controller function completing booking
    booking = query("""SELECT b.user_id, u.email, p.package_name FROM bookings b
                       JOIN users u ON u.user_id=b.user_id JOIN packages p ON p.package_id=b.package_id
                       WHERE b.booking_id=%s AND b.status='Approved'""", (request.form["id"],), one=True)  # Fetch booking
    if not booking:  # Validate booking is approved
        flash("Only approved bookings can be completed.", "error")  # Validation message
        return redirect(url_for("manage_bookings"))  # Return to list
    execute("UPDATE bookings SET status='Completed' WHERE booking_id=%s", (request.form["id"],))  # Update status in DB
    notify_user(booking["user_id"], booking["email"], "Trip completed",  # Send completion email asking for review
                f"Your {booking['package_name']} trip is complete. Please share your review.")  # Message body
    flash("Booking marked as completed.", "success")  # Feedback
    return redirect(url_for("manage_bookings"))  # Return to list

# Define route to view customer support issue reports
@app.route("/admin/reports")  # Accessible at /admin/reports
@admin_required  # Requires admin access
def manage_user_reports():  # Controller function listing customer tickets
    reports = query("""
        SELECT r.*, u.full_name, u.email FROM user_reports r
        JOIN users u ON r.user_id=u.user_id
        ORDER BY r.created_at DESC
    """)  # Fetch support reports joined with user details
    return render_template("admin_list.html", page_type="user_reports", reports=reports, page_title="User Reports")  # Render reports view

# Define route to update the resolution status of a support ticket
@app.route("/admin/reports/update", methods=["POST"])  # Accessible via POST
@admin_required  # Requires admin access
def update_user_report_status():  # Controller function updating ticket status
    execute("UPDATE user_reports SET status=%s WHERE report_id=%s",  # Updates status column in user_reports table
            (request.form["status"], request.form["id"]))  # Binds new status and report ID
    flash("Report status updated.", "success")  # Feedback to admin
    return redirect(url_for("manage_user_reports"))  # Return to reports list
