# Import date class to validate and compare travel dates against today's date
from datetime import date  # Used for date parsing and ensuring travel dates are in the future

# Import Decimal and InvalidOperation for precise financial budget calculations without floating-point errors
from decimal import Decimal, InvalidOperation  # Used to safely parse and validate budget amounts

# Import render_template to render HTML views and request to inspect URL query string arguments
from flask import render_template, request  # Core Flask functions for template rendering and request inputs

# Import the shared Flask app instance and SQL query execution helper
from extensions import app, query  # Gives access to route registration and database queries

# Define the root URL route for the homepage of the website
@app.route("/")  # Maps the root URL '/' to the home view function
def home():  # Controller function responsible for rendering the homepage
    # Query database for all travel packages that have not yet expired, ordered newest first
    packages = query("""SELECT * FROM packages
                        WHERE start_date IS NULL OR start_date >= CURRENT_DATE
                        ORDER BY created_at DESC""")  # Retrieves active travel packages from PostgreSQL

    # Extract the first 6 packages to display in the main 'Featured Packages' hero section
    featured_packages = packages[:6]  # Slices top 6 latest packages

    # Sort packages by price in ascending order and take the top 3 most affordable as 'Best Sellers'
    best_sellers = sorted(packages, key=lambda p: float(p["price"] or 0))[:3]  # Low-price budget deals

    # Filter packages that match popular weekend getaway destinations (Goa, Coorg, Ooty, etc.)
    weekend_getaways = [p for p in packages if p["destination_name"] and any(
        k in p["destination_name"].lower() for k in ["goa", "coorg", "ooty", "lonavala", "gokarna"]
    )][:3]  # Selects up to 3 weekend destinations

    # Filter packages accommodating groups of 4 or more travelers as family-friendly packages
    family_trips = [p for p in packages if (p["travelers_limit"] or 0) >= 4][:3]  # Family vacations

    # Filter premium luxury packages priced at ₹30,000 or more
    luxury_trips = [p for p in packages if float(p["price"] or 0) >= 30000][:3]  # High-end luxury trips

    # Fill any empty category slots with general packages so sections are never empty
    for category_list in [weekend_getaways, family_trips, luxury_trips]:  # Loops over curated categories
        for p in packages:  # Checks available packages
            if p not in category_list:  # Prevents duplicate entries in the same section
                category_list.append(p)  # Adds fallback package
            if len(category_list) == 3:  # Ensures exactly 3 packages per category section
                break  # Stops once minimum 3 items are present

    # Define platform statistics and trust badges displayed on the homepage
    stats = {"destinations": 500, "happy_travelers": 12000, "rating": "4.9/5", "free_cancellation": True}  # Platform highlights

    # Render homepage.html template passing all curated package collections and trust stats
    return render_template("homepage.html", featured_packages=featured_packages,
                           best_sellers=best_sellers, weekend_getaways=weekend_getaways,
                           family_trips=family_trips, luxury_trips=luxury_trips,
                           packages=packages, stats=stats)  # Injects variables into Jinja template

# Define search routes supporting both '/search' and '/search-results' URLs
@app.route("/search")  # Maps /search URL
@app.route("/search-results", endpoint="search_results")  # Maps alternate /search-results URL
def search_packages():  # Controller function handling package filter searches
    # Retrieve and sanitize destination query parameter from URL query string
    dest = request.args.get("destination", "").strip()  # Extracts destination filter string

    # Retrieve and sanitize budget query parameter from URL query string
    budget = request.args.get("budget", "").strip()  # Extracts maximum budget string

    # Retrieve and sanitize number of travelers query parameter from URL query string
    travelers = request.args.get("travelers", "").strip()  # Extracts traveler count string

    # Retrieve and sanitize travel date query parameter from URL query string
    travel_date = request.args.get("travel_date", "").strip()  # Extracts travel date string

    # Assemble search criteria into dictionary to re-populate search inputs in the template
    criteria = dict(destination=dest, budget=budget, travelers=travelers, travel_date=travel_date)  # Keeps form inputs

    # Identify any required search fields that were left empty by the user
    missing = [label for label, val in [("destination", dest), ("travel date", travel_date),
                                         ("budget", budget), ("number of travelers", travelers)] if not val]  # Checks for missing inputs

    # If any required fields are missing, return early with an informative validation error
    if missing:  # If required parameters are missing
        return render_template("search_results.html", packages=[], criteria=criteria,
                               error=f"Please enter: {', '.join(missing)}."), 400  # Returns 400 Bad Request

    # Validate that travel date is formatted as a valid ISO calendar date (YYYY-MM-DD)
    try:  # Try parsing the date string
        travel_date_value = date.fromisoformat(travel_date)  # Converts string to datetime.date object
    except ValueError:  # Raised if date format is invalid
        return render_template("search_results.html", packages=[], criteria=criteria,
                               error="Please choose a valid travel date."), 400  # Returns error for invalid date

    # Ensure selected travel date is not in the past
    if travel_date_value < date.today():  # Compares against today's date
        return render_template("search_results.html", packages=[], criteria=criteria,
                               error="Travel date must be today or a future date."), 400  # Rejects past dates

    # Initialize budget variable
    budget_value = None  # Holds validated numeric budget

    # Parse and validate numerical budget if provided
    if budget:  # If user supplied budget
        try:  # Safely parse decimal number
            budget_value = Decimal(budget)  # Converts budget to exact Decimal
            if not budget_value.is_finite() or budget_value <= 0:  # Rejects zero, negative, or infinity
                raise InvalidOperation  # Triggers exception on invalid values
        except InvalidOperation:  # Handles non-numeric or non-positive input
            return render_template("search_results.html", packages=[], criteria=criteria,
                                   error="Budget must be a valid number greater than zero."), 400  # Error response

    # Initialize travelers count variable
    travelers_value = None  # Holds validated integer traveler count

    # Parse and validate traveler count as a positive integer
    if travelers:  # If user supplied traveler count
        try:  # Safely parse integer
            travelers_value = int(travelers)  # Converts string to int
            if travelers_value < 1:  # Must be at least 1 person
                raise ValueError  # Triggers exception on negative or zero
        except ValueError:  # Handles non-numeric or zero input
            return render_template("search_results.html", packages=[], criteria=criteria,
                                   error="Travelers must be a whole number of at least 1."), 400  # Error response

    # Build parameterized SQL query dynamically based on search filters
    sql = "SELECT * FROM packages WHERE 1=1"  # Base SQL condition allowing flexible AND clauses
    params = []  # List of query parameters to prevent SQL injection

    # Filter destination by case-insensitive substring matching
    if dest:  # If destination filter specified
        sql += " AND LOWER(destination_name) LIKE LOWER(%s)"  # Append SQL LIKE condition
        params.append(f"%{dest}%")  # Safely bind wildcard parameter

    # Filter packages with price less than or equal to user budget
    if budget_value is not None:  # If budget filter active
        sql += " AND price <= %s"  # Append SQL maximum price condition
        params.append(budget_value)  # Safely bind budget value

    # Filter packages that can accommodate at least the requested number of travelers
    if travelers_value is not None:  # If traveler count filter active
        sql += " AND travelers_limit >= %s"  # Append SQL capacity condition
        params.append(travelers_value)  # Safely bind traveler capacity

    # Filter packages whose scheduled start date is on or after the requested travel date
    sql += " AND (start_date IS NULL OR start_date >= %s)"  # Package available on or after requested date
    params.append(travel_date_value)  # Safely bind travel date parameter

    # Execute dynamic search query in the database
    packages = query(sql, params)  # Runs parameterized SQL query

    # Render search results page with matching packages and search criteria
    return render_template("search_results.html", packages=packages, criteria=criteria)  # Displays search results
