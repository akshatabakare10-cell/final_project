# Import the shared Flask application instance created in extensions.py
from extensions import app  # Loads the configured Flask app, secret keys, and database settings

# Import public routes (homepage, search, viewing packages) to attach them to the Flask app
import routes.public  # Registers public guest-facing URL endpoints with the app

# Import authentication routes (user login, registration, password reset, logout)
import routes.auth  # Registers login and sign-up URL endpoints with the app

# Import user routes (user dashboard, profile update, wishlist, booking history)
import routes.user  # Registers logged-in customer account URL endpoints with the app

# Import API routes (AJAX/fetch endpoints for dynamic hotel and package queries)
import routes.api  # Registers JSON API URL endpoints for client-side JavaScript calls

# Import planner routes (custom itinerary generator and trip budget calculator)
import routes.planner  # Registers interactive trip planner URL endpoints with the app

# Import booking routes (package booking, seat selection, checkout, payment, invoice receipt)
import routes.booking  # Registers reservation and payment URL endpoints with the app

# Import admin routes (management dashboard, CRUD for hotels, transport, packages, bookings)
import routes.admin  # Registers admin panel URL endpoints for managing the system

# Check if this Python script is being executed directly (as the main program) rather than being imported
if __name__ == "__main__":  # Ensures the server only starts when running 'python app.py' directly
    # Run the Flask local web server with debug mode enabled on port 5000
    app.run(debug=True, port=5000)  # Starts the live development server at http://127.0.0.1:5000
