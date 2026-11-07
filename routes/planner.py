# Import json module to serialize complex itinerary dictionaries into JSON strings for database storage
import json  # Used for converting itinerary structures to text for SQL insertion

# Import Flask view helpers for template rendering, form input reading, session data, and flash alerts
from flask import render_template, request, session, flash  # Handles web views and messages

# Import application instance, SQL helpers, auth guard, and logger from extensions
from extensions import app, query, get_db, login_required, logger  # Access to database, security, and logging

# Function to construct a personalized day-by-day travel plan based on traveler preferences
def build_trip_plan(destination, days, travelers, budget, trip_style):  # Algorithm generating itinerary
    destination_text = (destination or "Your destination").strip() or "Your destination"  # Sanitizes destination text
    days_value = max(1, int(days or 1))  # Ensures positive trip duration of at least 1 day
    travelers_value = max(1, int(travelers or 1))  # Ensures at least 1 traveler
    budget_value = max(float(budget or 0), 0)  # Ensures non-negative budget value
    trip_style_name = (trip_style or "Balanced").strip() or "Balanced"  # Default trip style category

    # Map selected travel style (Adventure, Luxury, Relax, Family, Balanced) to tailored activities
    activities = {  # Dictionary mapping style names to activities
        "Adventure": "a scenic trek and local adventure activities",  # Outdoor thrill activities
        "Luxury": "a private transfer and a relaxed spa evening",  # High-end pampered experiences
        "Family": "a beach day and a kid-friendly museum visit",  # Activities suitable for children and groups
        "Relax": "a sunrise walk and a quiet wellness session",  # Peaceful restorative schedule
        "Balanced": "local sightseeing and a cultural stop",  # General mix of highlights
    }.get(trip_style_name, "local sightseeing and a cultural stop")  # Fallback to balanced if unknown

    # Calculate average daily spending allowance based on total budget and trip duration
    cost_per_day = round(budget_value / days_value, 2) if budget_value else 1500  # Default ₹1500/day if budget is 0
    # Build list of daily itinerary cards for each day of the vacation
    itinerary = [  # List comprehension generating day-by-day breakdown
        {  # Dictionary representing a single day's plan
            "day": day_number,  # Day number index (Day 1, Day 2, etc.)
            "title": f"Day {day_number}: Explore {destination_text}",  # Day heading
            "plan": f"Enjoy {activities}, with free time in the evening for dining and rest.",  # Activity description
            "cost": cost_per_day,  # Estimated daily expense
        }  # End of day dict
        for day_number in range(1, days_value + 1)  # Loops from 1 through total days
    ]  # Complete itinerary list

    # General travel advice and preparation tips for the customer
    recommendations = [  # Helpful tips list
        "Book stays and transport early for the best pricing.",  # Advance booking recommendation
        "Keep a small daily buffer for local shopping and surprises.",  # Budget safety margin
    ]  # End of recommendations list

    # Return structured trip plan dictionary
    return {  # Trip plan payload
        "destination": destination_text, "days": days_value, "travelers": travelers_value,  # Core trip parameters
        "budget": budget_value, "trip_style": trip_style_name, "itinerary": itinerary,  # Financials and schedule
        "recommendations": recommendations,  # Travel tips
        "total_estimate": round(cost_per_day * days_value, 2),  # Projected grand total cost
    }  # End of return dictionary

# Function to save a generated trip plan permanently into PostgreSQL database
def save_trip_plan(user_id, destination, days, travelers, budget, trip_style, plan_data):  # Persists plan to DB
    if not user_id:  # Verify user is logged in
        return None  # Cannot save without a valid user account
    payload = {  # Assembles plan details for JSON storage
        "destination": plan_data.get("destination") if plan_data else destination,  # Destination location
        "days": plan_data.get("days") if plan_data else days,  # Number of days
        "travelers": plan_data.get("travelers") if plan_data else travelers,  # Traveler headcount
        "budget": plan_data.get("budget") if plan_data else budget,  # Budget amount
        "trip_style": plan_data.get("trip_style") if plan_data else trip_style,  # Travel vibe
        "itinerary": plan_data.get("itinerary", []) if plan_data else [],  # Detailed daily schedule
        "recommendations": plan_data.get("recommendations", []) if plan_data else [],  # Tips
        "total_estimate": plan_data.get("total_estimate") if plan_data else 0,  # Estimated total price
    }  # End of payload dictionary
    try:  # Wraps in try block to catch SQL insertion errors
        with get_db() as conn:  # Connects to database
            cur = conn.cursor()  # Gets SQL cursor
            cur.execute(  # Executes INSERT statement
                """INSERT INTO trip_plans (user_id,destination,trip_style,days,travelers,budget,total_estimate,itinerary_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING plan_id""",  # Inserts record and returns new ID
                (user_id, payload["destination"], payload["trip_style"], payload["days"],  # Binds parameters safely
                 payload["travelers"], payload["budget"], payload["total_estimate"], json.dumps(payload)))  # Converts payload to JSON
            return cur.fetchone()[0]  # Returns generated plan_id primary key
    except Exception:  # Catches database connection or execution failures
        logger.exception("Unable to save trip plan")  # Logs error traceback
        return None  # Returns None if saving failed

# Define interactive trip planner route supporting GET (view form) and POST (generate & save plan)
@app.route("/planner", methods=["GET", "POST"])  # Accessible at /planner
@login_required  # Restricts access to authenticated users
def planner():  # Controller function managing the trip planner interface
    uid = session["user_id"]  # Retrieves logged-in user ID
    plan = None  # Holds currently generated plan (defaults to None on initial page load)
    saved_plans = query("SELECT * FROM trip_plans WHERE user_id=%s ORDER BY created_at DESC", (uid,))  # Fetches previous plans

    if request.method == "POST":  # User submitted trip criteria form
        destination = request.form.get("destination", "").strip()  # Extracts destination input
        days = request.form.get("days", "3").strip()  # Extracts number of days input
        travelers = request.form.get("travelers", "1").strip()  # Extracts traveler count
        budget = request.form.get("budget", "").strip()  # Extracts total budget input
        trip_style = request.form.get("trip_style", "Balanced").strip()  # Extracts style preference

        if not destination:  # Validates destination is not empty
            flash("Please enter a destination before generating a trip plan.", "error")  # Shows validation error
        else:  # Destination was provided
            try:  # Validate numeric conversions
                days_value = int(days)  # Parses days as integer
                travelers_value = int(travelers)  # Parses travelers as integer
                budget_value = float(budget)  # Parses budget as floating point number
                if days_value < 1 or travelers_value < 1 or budget_value <= 0:  # Ensures positive non-zero values
                    raise ValueError  # Rejects zero or negative numbers
                plan = build_trip_plan(destination, days_value, travelers_value, budget_value, trip_style)  # Generates plan
                saved_plan_id = save_trip_plan(uid, destination, days_value, travelers_value, budget_value, trip_style, plan)  # Saves to DB
                if saved_plan_id:  # If successfully saved to database
                    flash("Saved to your dashboard.", "success")  # Feedback to user
                    plan["saved_plan_id"] = saved_plan_id  # Attach plan ID to dictionary
                else:  # If save failed
                    flash("Trip plan generated. It is ready to review.", "success")  # Fallback feedback
            except ValueError:  # Handles invalid number formatting
                flash("Please enter valid positive values for trip days, travelers, and budget.", "error")  # Error message

    return render_template("planner.html", plan=plan, saved_plans=saved_plans, user_name=session.get("user_name", ""))  # Renders planner template
