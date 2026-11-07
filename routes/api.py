# Import jsonify to convert Python dictionaries or lists into JSON responses, and session for user tracking
from flask import jsonify, session  # Provides JSON response serialization and access to logged-in user session

# Import Flask app instance, database query runner, and login security decorator from extensions
from extensions import app, query, login_required  # Shared app object, safe SQL query helper, and auth guard

# Define URL route to fetch available travel packages in JSON format for frontend JavaScript
@app.route("/api/packages")  # Endpoint accessible at GET /api/packages
def api_packages():  # Controller function returning package list
    # Query database for upcoming or evergreen travel packages ordered with newest first
    rows = query("""SELECT package_id,package_name,destination_name,duration,price,seats_available,start_date
                    FROM packages WHERE start_date IS NULL OR start_date >= CURRENT_DATE ORDER BY created_at DESC""")  # Executes SELECT SQL
    # Convert database rows into a JSON array of objects and return as HTTP response
    return jsonify([dict(row) for row in rows])  # Serializes row dictionaries into JSON format

# Define URL route to fetch customer reviews for a specific package identified by package_id
@app.route("/api/reviews/<int:package_id>")  # Dynamic URL containing integer package_id
def api_reviews(package_id):  # Controller function taking package_id from URL path
    # Query reviews table for all feedback matching this package ID, sorted newest first
    rows = query("SELECT rating,comment,created_at FROM package_reviews WHERE package_id=%s ORDER BY created_at DESC", (package_id,))  # Parameterized SQL query
    # Convert reviews to JSON array and return to client
    return jsonify([dict(row) for row in rows])  # Returns JSON list of review objects

# Define URL route to fetch the current logged-in user's booking history as JSON
@app.route("/api/bookings")  # Endpoint accessible at GET /api/bookings
@login_required  # Protects endpoint so only authenticated users can access their booking data
def api_bookings():  # Controller function for user bookings API
    # Query bookings database table for bookings belonging to the currently logged-in user_id
    rows = query("SELECT booking_id,package_id,travel_date,travelers,total_price,status FROM bookings WHERE user_id=%s ORDER BY booking_date DESC",
                 (session["user_id"],))  # Uses session['user_id'] to isolate user's private data
    # Serialize bookings into JSON array and return to client
    return jsonify([dict(row) for row in rows])  # Returns JSON list of bookings
