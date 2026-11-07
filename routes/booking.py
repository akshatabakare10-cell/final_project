# Import uuid to generate unique, secure transaction IDs for customer payments
import uuid  # Used for unique transaction reference numbers like 'TW-20260909-ABC123XYZ'

# Import datetime, date, and timezone for manipulating calendar dates, checking booking expiries, and UTC stamps
from datetime import datetime, date, timezone  # Used for date validations and timestamps

# Import Flask template rendering, form handling, redirects, sessions, flash messages, and response objects
from flask import render_template, request, redirect, url_for, session, flash, make_response  # Web handling tools

# Import app instance, SQL query runners, database connection, auth guard, notifications, and audit logging
from extensions import app, query, execute, get_db, login_required, notify_user, audit  # App and DB utilities

# Define route to display all available travel packages for browsing and booking
@app.route("/booking")  # Accessible at /booking
@app.route("/packages", endpoint="packages")  # Also accessible via /packages
def booking():  # Controller function showing packages catalog
    # Retrieve all packages where start date is either evergreen (NULL) or in the future, newest first
    packages = query("""SELECT * FROM packages
                        WHERE start_date IS NULL OR start_date >= CURRENT_DATE
                        ORDER BY created_at DESC""")  # Executes SELECT SQL query
    # Render booking.html template passing the retrieved packages and username
    return render_template("booking.html", packages=packages, user_name=session.get("user_name", ""))  # Shows package cards

# Define route to initialize a package booking when traveler clicks 'Book Now'
@app.route("/book/<int:package_id>", methods=["POST"])  # Handles POST form submission for specific package ID
@login_required  # Requires customer login
def book_package(package_id):  # Controller creating or updating pending booking
    uid = session["user_id"]  # Extract user ID from session
    travel_date = request.form.get("travel_date") or None  # Extract desired travel date
    try:  # Validate traveler count input
        travelers = int(request.form.get("travelers", 1))  # Parse number of people
    except ValueError:  # Handles non-integer input
        flash("Travelers must be a whole number.", "error")  # Error alert
        return redirect(url_for("booking"))  # Redirect to package list

    package = query("SELECT * FROM packages WHERE package_id=%s", (package_id,), one=True)  # Fetch package record
    if not package:  # Validate package exists
        flash("Package not found.", "error")  # Error message
        return redirect(url_for("booking"))  # Redirect
    if package["start_date"] and package["start_date"] < date.today():  # Ensure package has not already departed
        flash("This package is no longer available.", "error")  # Expired alert
        return redirect(url_for("booking"))  # Redirect

    if travel_date:  # If user selected a travel date
        try:  # Validate ISO format
            selected_date = date.fromisoformat(travel_date)  # Convert string to date object
        except ValueError:  # Raised on malformed date string
            flash("Please choose a valid travel date.", "error")  # Format error
            return redirect(url_for("package_details", package_id=package_id))  # Return to details
        if selected_date < date.today():  # Reject past dates
            flash("Travel date must be today or a future date.", "error")  # Date error
            return redirect(url_for("package_details", package_id=package_id))  # Return to details

    if travelers < 1 or travelers > (package["travelers_limit"] or 10):  # Check traveler capacity limits
        flash("Please choose a valid number of travelers for this package.", "error")  # Capacity error
        return redirect(url_for("package_details", package_id=package_id))  # Return to details

    if package.get("seats_available") is not None and travelers > package["seats_available"]:  # Verify sufficient seats remain
        flash("Not enough seats are available for this package.", "error")  # Sold out error
        return redirect(url_for("package_details", package_id=package_id))  # Return to details

    total = float(package["price"]) * travelers  # Calculate total price (price per person * travelers)
    existing = query("SELECT booking_id FROM bookings WHERE user_id=%s AND package_id=%s AND status='Pending'",  # Check if pending booking already exists
                     (uid, package_id), one=True)  # Check for uncompleted booking
    if existing:  # If pending booking exists, update it rather than creating a duplicate
        execute("UPDATE bookings SET travel_date=%s, travelers=%s, total_price=%s WHERE booking_id=%s",  # Update existing record
                (travel_date, travelers, total, existing["booking_id"]))  # Binds updated values
        session["booking_id"] = existing["booking_id"]  # Store active booking ID in session
    else:  # Create a brand new pending booking
        with get_db() as conn:  # Open database connection
            cur = conn.cursor()  # Get cursor
            cur.execute("""INSERT INTO bookings (user_id,package_id,travel_date,travelers,total_price)
                           VALUES (%s,%s,%s,%s,%s) RETURNING booking_id""",  # Insert booking and return generated ID
                        (uid, package_id, travel_date, travelers, total))  # Safely bind values
            session["booking_id"] = cur.fetchone()[0]  # Store new booking ID in user session

    return redirect(url_for("checkout"))  # Seamlessly progresses user to checkout/payment page

# Define route to view full package details, overview, and reviews
@app.route("/package/<int:package_id>")  # Dynamic route with package ID
def package_details(package_id):  # Controller showing full package view
    uid = session.get("user_id")  # Current user ID (None if guest)
    user = query("SELECT * FROM users WHERE user_id=%s", (uid,), one=True) if uid else None  # Fetch user profile if logged in
    package = query("SELECT * FROM packages WHERE package_id=%s", (package_id,), one=True)  # Fetch package
    if not package:  # If package does not exist
        return render_template("error.html", message="Package not found."), 404  # Return 404 error page

    package_hotel = query("SELECT * FROM hotels WHERE hotel_id=%s", (package["hotel_id"],), one=True) if package.get("hotel_id") else None  # Fetch hotel
    package_transport = query("SELECT * FROM transport WHERE transport_id=%s", (package["transport_id"],), one=True) if package.get("transport_id") else None  # Fetch transport

    destination = package.get("destination_name") or "Your dream escape"  # Destination name
    itinerary = [  # Default tour schedule highlights
        f"Arrival at {destination} and seamless transfer to your stay",  # Day 1 arrival
        "Curated sightseeing with local highlights and guided experiences",  # Day 2 sightseeing
        "Free time for leisure, shopping, or optional adventures",  # Day 3 leisure
        "Cultural dinner, premium stay, and travel support throughout the trip",  # Day 4 farewell
    ]  # Tour timeline
    inclusions = [  # Items included in package price
        "Comfort stay with breakfast and curated local experiences",  # Hotel & breakfast
        "Return transfers or airport pickup as applicable",  # Transit
        "Tour planning support and 24/7 assistance",  # Concierge
        "Entry tickets or destination activity support",  # Sightseeing tickets
    ]  # Inclusions list
    exclusions = [  # Items not included in package price
        "Flights and personal shopping expenses",  # Personal shopping
        "Optional adventure activities priced separately",  # Add-ons
        "Travel insurance and visa fees",  # Legal & insurance
    ]  # Exclusions list
    faqs = [  # Frequently asked questions for travelers
        {"question": "Can I customize this trip?", "answer": "Yes, our team can adjust travel dates, room preferences, and add-on experiences for eligible packages."},  # FAQ 1
        {"question": "Is this package suitable for families?", "answer": "Most packages are designed for families and small groups; travelers can check the group limit and ideal trip style on the package summary."},  # FAQ 2
        {"question": "What is the cancellation policy?", "answer": "Cancellations are reviewed based on departure timing, but most packages include a flexible cancellation window before final confirmation."},  # FAQ 3
    ]  # FAQs list
    best_time = "Ideal between October and March for comfortable weather and smoother sightseeing."  # Travel tip

    selected_package = None  # Holds active booking object
    booking_id = session.get("booking_id")  # Read active booking ID from session
    if booking_id and uid:  # If user has an active pending booking
        selected_package = query("""
            SELECT b.*, p.package_name, p.destination_name
            FROM bookings b JOIN packages p ON b.package_id=p.package_id
            WHERE b.booking_id=%s AND b.user_id=%s
        """, (booking_id, uid), one=True)  # Retrieve booking info

    reviews = query("""SELECT r.*, u.full_name FROM package_reviews r
                       JOIN users u ON u.user_id=r.user_id
                       WHERE r.package_id=%s ORDER BY r.created_at DESC LIMIT 10""", (package_id,))  # Fetch 10 recent reviews
    review_summary = query("""
        SELECT COUNT(*) AS review_count, COALESCE(AVG(rating), 0) AS average_rating
        FROM package_reviews WHERE package_id=%s
    """, (package_id,), one=True)  # Calculate review count and average rating

    reviewable_booking = None  # Default None
    if uid:  # Only verify review eligibility for logged-in users
        reviewable_booking = query("""SELECT booking_id FROM bookings
                                     WHERE user_id=%s AND package_id=%s
                                     AND status IN ('Approved', 'Completed')
                                     ORDER BY booking_date DESC LIMIT 1""", (uid, package_id), one=True)  # Only travelers who completed/approved can review
    existing_review = None  # Holds user's previous review if submitted
    if reviewable_booking and uid:  # If traveler qualifies to write a review
        existing_review = query("SELECT * FROM package_reviews WHERE user_id=%s AND booking_id=%s",  # Check for existing review
                                (uid, reviewable_booking["booking_id"]), one=True)  # Single review record

    return render_template("package.html", package=package, package_hotel=package_hotel,  # Render package detail template
                           package_transport=package_transport, user=user, selected_package=selected_package,  # Add-ons and user
                           reviews=reviews, review_summary=review_summary,  # Ratings and comments
                           reviewable_booking=reviewable_booking, existing_review=existing_review,  # Review privileges
                           itinerary=itinerary, inclusions=inclusions, exclusions=exclusions,  # Highlights
                           faqs=faqs, best_time=best_time, destination=destination)  # FAQs and metadata

# Define route to submit or update a review for a package
@app.route("/package/<int:package_id>/review", methods=["POST"])  # Dynamic POST route
@login_required  # Requires customer authentication
def submit_package_review(package_id):  # Controller handling review submission
    uid = session["user_id"]  # Logged in user ID
    try:  # Parse integer rating
        rating = int(request.form.get("rating", "0"))  # Rating 1-5
    except ValueError:  # Invalid format
        rating = 0  # Default 0
    comment = request.form.get("comment", "").strip()  # Review comment text
    booking_id = request.form.get("booking_id", "")  # Reference booking ID

    booking = query("""SELECT booking_id FROM bookings WHERE booking_id=%s AND user_id=%s
                       AND package_id=%s AND status IN ('Approved', 'Completed')""",  # Verify valid completed/approved booking
                    (booking_id, uid, package_id), one=True)  # Authenticate booking ownership

    if not booking or rating not in range(1, 6) or not comment or len(comment) > 1000:  # Validate rating range and comment length
        flash("Please provide a 1–5 rating and a review of up to 1,000 characters.", "error")  # Feedback
        return redirect(url_for("package_details", package_id=package_id))  # Return

    execute("""INSERT INTO package_reviews (user_id,package_id,booking_id,rating,comment)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (user_id,booking_id) DO UPDATE SET rating=EXCLUDED.rating,
               comment=EXCLUDED.comment, updated_at=NOW()""",  # Upsert review record
            (uid, package_id, booking["booking_id"], rating, comment))  # Bind parameters safely
    flash("Thanks—your review has been saved.", "success")  # Feedback
    return redirect(url_for("package_details", package_id=package_id))  # Redirect to package details

# Define route to save hotel room add-on selection for active booking
@app.route("/save-hotel", methods=["POST"])  # Accessible via POST
@login_required  # Requires authentication
def save_package_hotel():  # Controller function saving hotel add-on
    uid = session["user_id"]  # User ID
    booking_id = session.get("booking_id")  # Active booking ID
    if not booking_id:  # Verify user has initiated a booking
        flash("No active booking.", "error")  # Error notice
        return redirect(url_for("booking"))  # Redirect to catalog

    hotel_id = request.form.get("hotel_id")  # Selected hotel ID
    hotel = query("SELECT * FROM hotels WHERE hotel_id=%s", (hotel_id,), one=True)  # Fetch hotel record
    if not hotel:  # Check hotel exists
        flash("Hotel not found.", "error")  # Error notice
        return redirect(url_for("booking"))  # Redirect

    fullname = request.form.get("fullname")  # Guest name
    email = request.form.get("email")  # Guest email
    checkin = request.form.get("checkin") or None  # Check-in date
    checkout = request.form.get("checkout") or None  # Check-out date
    room_type = request.form.get("roomtype", "Deluxe")  # Room category

    nights = 1  # Default 1 night
    if checkin and checkout:  # If both dates entered
        try:  # Calculate duration in nights
            d1 = datetime.strptime(checkin, "%Y-%m-%d")  # Parse check-in date
            d2 = datetime.strptime(checkout, "%Y-%m-%d")  # Parse check-out date
            nights = max(1, (d2 - d1).days)  # Compute days difference
        except Exception:  # Fallback on invalid format
            pass  # Retain default 1 night

    total = float(hotel["price_per_night"]) * nights  # Compute total hotel price (rate * nights)
    existing = query("SELECT hotel_booking_id FROM hotel_bookings WHERE booking_id=%s AND user_id=%s",  # Check for existing hotel booking
                     (booking_id, uid), one=True)  # Check record
    if existing:  # Update existing hotel selection
        execute("""UPDATE hotel_bookings SET hotel_id=%s,full_name=%s,email=%s,
                   checkin=%s,checkout=%s,room_type=%s,total_price=%s
                   WHERE hotel_booking_id=%s""",  # Update query
                (hotel_id, fullname, email, checkin, checkout, room_type, total, existing["hotel_booking_id"]))  # Bind values
    else:  # Insert new hotel booking selection
        execute("""INSERT INTO hotel_bookings (user_id,booking_id,hotel_id,full_name,email,
                   checkin,checkout,room_type,total_price)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",  # Insert query
                (uid, booking_id, hotel_id, fullname, email, checkin, checkout, room_type, total))  # Bind values

    flash("Hotel details saved!", "success")  # Feedback
    booking = query("SELECT package_id FROM bookings WHERE booking_id=%s", (booking_id,), one=True)  # Fetch package ID
    return redirect(url_for("package_details", package_id=booking["package_id"]))  # Return to package page

# Define route to save transport add-on selection for active booking
@app.route("/save-transport", methods=["POST"])  # Accessible via POST
@login_required  # Requires login
def save_package_transport():  # Controller function saving transport add-on
    uid = session["user_id"]  # User ID
    booking_id = session.get("booking_id")  # Booking ID
    if not booking_id:  # Verify active booking
        flash("No active booking.", "error")  # Alert
        return redirect(url_for("booking"))  # Redirect

    mode = request.form.get("mode_name")  # Transport mode (Flight, Train, Car Rental)
    transport = query("SELECT * FROM transport WHERE mode=%s LIMIT 1", (mode,), one=True)  # Look up transport record
    transport_id = transport["transport_id"] if transport else None  # Extract ID
    price = float(transport["price"]) if transport else 0  # Extract price

    from_loc = request.form.get("from_city") or request.form.get("from_station") or request.form.get("pickup_location") or ""  # Departure origin
    to_loc = request.form.get("to_city") or request.form.get("to_station") or request.form.get("destination") or ""  # Arrival destination
    airport = request.form.get("airport", "")  # Airport name if flight
    travel_date = request.form.get("departure_date") or request.form.get("travel_date") or None  # Departure date
    pickup_date = request.form.get("pickup_date") or None  # Pickup date
    pickup_time = request.form.get("pickup_time") or None  # Pickup time
    return_date = request.form.get("return_date") or None  # Return trip date
    passengers = int(request.form.get("passengers", 1))  # Passenger count
    travel_class = request.form.get("flight_class") or request.form.get("travel_class") or request.form.get("car_type") or ""  # Seating class

    existing = query("SELECT transport_booking_id FROM transport_bookings WHERE booking_id=%s AND user_id=%s",  # Check if transport already selected
                     (booking_id, uid), one=True)  # Query record
    if existing:  # Update existing transport record
        execute("""UPDATE transport_bookings SET transport_id=%s,mode=%s,from_location=%s,to_location=%s,
                   airport_name=%s,travel_date=%s,pickup_date=%s,pickup_time=%s,return_date=%s,
                   passengers=%s,travel_class=%s,total_price=%s
                   WHERE transport_booking_id=%s""",  # Update SQL
                (transport_id, mode, from_loc, to_loc, airport, travel_date, pickup_date,  # Bound parameters
                 pickup_time, return_date, passengers, travel_class, price, existing["transport_booking_id"]))  # Bound parameters
    else:  # Insert new transport selection record
        execute("""INSERT INTO transport_bookings (user_id,booking_id,transport_id,mode,from_location,to_location,
                   airport_name,travel_date,pickup_date,pickup_time,return_date,passengers,travel_class,total_price)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",  # Insert SQL
                (uid, booking_id, transport_id, mode, from_loc, to_loc, airport, travel_date,  # Bound parameters
                 pickup_date, pickup_time, return_date, passengers, travel_class, price))  # Bound parameters

    flash("Transport details saved!", "success")  # Feedback
    booking = query("SELECT package_id FROM bookings WHERE booking_id=%s", (booking_id,), one=True)  # Fetch package ID
    return redirect(url_for("package_details", package_id=booking["package_id"]))  # Return to package page

# Helper function to compute complete itemized checkout summary across package, hotel, and transport
def build_checkout_summary(uid, booking_id):  # Aggregates costs for payment screen
    checkout = dict(package_booking=None, hotel_booking=None, transport_booking=None, total_amount=0)  # Initial summary structure
    total = 0.0  # Running cost accumulator

    pkg_b = query("""
        SELECT b.*, p.package_name, b.total_price, b.travelers, b.travel_date
        FROM bookings b JOIN packages p ON b.package_id=p.package_id
        WHERE b.booking_id=%s AND b.user_id=%s
    """, (booking_id, uid), one=True)  # Fetch package booking details

    if pkg_b:  # If package booking exists
        lines = [f"{pkg_b['travelers']} traveler(s) × ₹{float(pkg_b['total_price']/pkg_b['travelers']):,.0f}"]  # Itemized line
        if pkg_b["travel_date"]:  # If travel date recorded
            lines.append(f"Travel: {pkg_b['travel_date']}")  # Add date line
        checkout["package_booking"] = dict(pkg_b)  # Attach package details
        checkout["package_booking"]["summary_lines"] = lines  # Attach readable lines
        total += float(pkg_b["total_price"] or 0)  # Add package cost to total

    hotel_b = query("""
        SELECT hb.*, h.hotel_name FROM hotel_bookings hb
        JOIN hotels h ON hb.hotel_id=h.hotel_id
        WHERE hb.booking_id=%s AND hb.user_id=%s
    """, (booking_id, uid), one=True)  # Fetch hotel add-on details

    if hotel_b:  # If hotel add-on exists
        lines = [f"{hotel_b['room_type']} Room",  # Room type line
                 f"Check-in: {hotel_b['checkin']} → Check-out: {hotel_b['checkout']}"]  # Dates line
        checkout["hotel_booking"] = dict(hotel_b)  # Attach hotel details
        checkout["hotel_booking"]["summary_lines"] = lines  # Attach lines
        total += float(hotel_b["total_price"] or 0)  # Add hotel cost to total

    trans_b = query("SELECT * FROM transport_bookings WHERE booking_id=%s AND user_id=%s",  # Fetch transport add-on
                    (booking_id, uid), one=True)  # Query record
    if trans_b:  # If transport add-on exists
        lines = [f"{trans_b.get('mode', 'Transport')}"]  # Mode line
        from_loc = trans_b.get("from_location")  # Origin
        to_loc = trans_b.get("to_location")  # Destination
        if from_loc or to_loc:  # If route specified
            lines.append(f"{from_loc or ''} → {to_loc or ''}".strip())  # Add route line
        checkout["transport_booking"] = dict(trans_b)  # Attach transport details
        checkout["transport_booking"]["summary_lines"] = lines  # Attach lines
        total += float(trans_b.get("total_price") or 0)  # Add transport cost to total

    checkout["total_amount"] = total  # Set final grand total amount
    return checkout  # Return complete checkout breakdown

# Define route to view order summary before payment
@app.route("/checkout")  # Accessible at /checkout
@login_required  # Requires login
def checkout():  # Controller function showing order summary
    uid = session["user_id"]  # User ID
    booking_id = session.get("booking_id")  # Active booking ID
    if not booking_id:  # Verify booking selected
        flash("Please select a package before going to checkout.", "error")  # Prompt user
        return redirect(url_for("booking"))  # Redirect to package catalog
    checkout_summary = build_checkout_summary(uid, booking_id)  # Generate itemized invoice breakdown
    return render_template("payment.html", checkout=checkout_summary)  # Render checkout page

# Define payment route supporting GET (view payment form) and POST (process transaction)
@app.route("/payment", methods=["GET", "POST"])  # Accessible at /payment
@login_required  # Requires customer login
def payment():  # Controller function processing payments
    uid = session["user_id"]  # Logged-in user ID
    booking_id = session.get("booking_id")  # Active booking ID
    if not booking_id:  # Validate booking exists
        flash("Please select a package before going to payment.", "error")  # Prompt user
        return redirect(url_for("booking"))  # Redirect to packages

    checkout = build_checkout_summary(uid, booking_id)  # Fetch current pricing breakdown
    total = float(checkout.get("total_amount") or 0)  # Extract grand total

    if request.method == "POST":  # User submitted payment form
        method = request.form.get("method", "cash")  # Selected payment gateway method (card, upi, bank, cash)
        if method not in {"card", "upi", "bank", "cash"}:  # Validate supported payment methods
            flash("Please choose a valid payment method.", "error")  # Error notice
            return redirect(url_for("payment"))  # Return
        if total <= 0:  # Validate positive payment total
            flash("No booking to pay for.", "error")  # Error notice
            return redirect(url_for("payment"))  # Return

        # Validate method-specific fields (cardholder name, UPI handle, or bank selection)
        if method == "card" and not request.form.get("card_name", "").strip():  # Card validation
            flash("Please enter the name on the card before paying.", "error")  # Prompt cardholder name
            return redirect(url_for("payment"))  # Return
        if method == "upi" and not request.form.get("upi", "").strip():  # UPI ID validation
            flash("Please enter a UPI ID before paying.", "error")  # Prompt UPI ID
            return redirect(url_for("payment"))  # Return
        if method == "bank" and not request.form.get("bank", "").strip():  # Net banking validation
            flash("Please select a bank before paying.", "error")  # Prompt bank selection
            return redirect(url_for("payment"))  # Return

        transaction_id = f"TW-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"  # Generate transaction code
        execute("""INSERT INTO payments (user_id,booking_id,amount,payment_method,status,transaction_id)
                   VALUES (%s,%s,%s,%s,'Paid',%s)""",  # Record completed payment in PostgreSQL
                (uid, booking_id, total, method, transaction_id))  # Binds payment details

        user = query("SELECT email FROM users WHERE user_id=%s", (uid,), one=True)  # Look up user email
        if user:  # If user email found
            notify_user(uid, user["email"], "Payment received",  # Send confirmation email and database alert
                        f"Payment {transaction_id} for {total:.2f} was received. Your booking is pending approval.")  # Notification body

        audit("payment_received", "payment", None, transaction_id)  # Log payment event in audit trail
        session.pop("booking_id", None)  # Clear active booking ID from session once paid
        flash("Payment successful! Booking is now pending admin approval.", "success")  # Feedback
        return redirect(url_for("user_dashboard"))  # Redirect customer to their dashboard

    return render_template("payment.html", checkout=checkout)  # Render payment interface

# Define route to view user's past transaction receipts
@app.route("/payment-history")  # Accessible at /payment-history
@login_required  # Requires login
def payment_history():  # Controller displaying past transactions
    uid = session["user_id"]  # Current user ID
    payments = query("SELECT * FROM payments WHERE user_id=%s ORDER BY payment_date DESC", (uid,))  # Fetch all user payments
    return render_template("payment_history.html", payments=payments)  # Render payment history template

# Define route to view or download official invoice receipt for a specific payment
@app.route("/receipt/<int:payment_id>")  # Dynamic route with payment ID
@login_required  # Requires login
def payment_receipt(payment_id):  # Controller generating printable receipt
    receipt = query("""SELECT pay.*, b.travel_date, b.travelers, b.total_price, p.package_name,
                              p.destination_name, u.full_name, u.email
                       FROM payments pay JOIN bookings b ON b.booking_id=pay.booking_id
                       JOIN packages p ON p.package_id=b.package_id JOIN users u ON u.user_id=pay.user_id
                       WHERE pay.payment_id=%s AND pay.user_id=%s""",  # Join payments, bookings, packages, and users
                    (payment_id, session["user_id"]), one=True)  # Ensures user can only access their own receipts
    if not receipt:  # If receipt does not exist or belongs to another user
        return render_template("error.html", message="Receipt not found."), 404  # Return 404 error

    response = make_response(render_template("receipt.html", receipt=receipt))  # Render receipt HTML
    if request.args.get("download") == "1":  # If user clicked 'Download Invoice'
        response.headers["Content-Disposition"] = f"attachment; filename=travelworld-receipt-{payment_id}.html"  # Trigger browser download
    return response  # Return receipt view or download response
