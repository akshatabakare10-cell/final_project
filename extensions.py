# Import os to read environment variables and interact with the operating system filesystem
import os  # Used for reading DB credentials, secret keys, and setting up file upload paths

# Import re for regular expression pattern matching (validating email addresses and passwords)
import re  # Used for checking formats like email syntax and password strength

# Import logging to output informational and error logs to the server terminal
import logging  # Used for recording errors, events, and audit logs during execution

# Import smtplib for sending automated email notifications using standard SMTP protocol
import smtplib  # Used to connect to email servers (like Gmail or Mailgun) to dispatch emails

# Import time for tracking timestamps and measuring elapsed time for rate limiting
import time  # Used to track time windows for failed login attempt rate limiting

# Import uuid to generate unique, random identifiers for uploaded image filenames
import uuid  # Used to prevent image file name collisions when multiple files are uploaded

# Import defaultdict and deque to efficiently track timestamps of failed login attempts
from collections import defaultdict, deque  # Used for sliding window in-memory rate limiting

# Import EmailMessage to construct MIME formatted email messages with headers and body
from email.message import EmailMessage  # Used to build subject, sender, recipient, and message body

# Import wraps to preserve original function signatures and docstrings when creating decorators
from functools import wraps  # Used in @login_required and @admin_required custom decorators

# Import timedelta to specify session expiration durations
from datetime import timedelta  # Used to set user session lifetime to 8 hours

# Import essential Flask modules for web app creation, templates, request handling, and sessions
from flask import Flask, render_template, request, redirect, url_for, session, flash  # Core Flask web tools

# Import psycopg2 driver to connect and interact with PostgreSQL database
import psycopg2  # The PostgreSQL adapter for Python

# Import psycopg2.extras to enable dictionary-like access to database query rows
import psycopg2.extras  # Allows accessing SQL columns by column name (e.g. row['user_id'])

# Import load_dotenv to read configuration variables from the local .env file
from dotenv import load_dotenv  # Automatically loads environment variables from .env on startup

# Import CSRFProtect to defend against Cross-Site Request Forgery security vulnerabilities
from flask_wtf import CSRFProtect  # Protects HTML forms from malicious third-party submissions

# Import secure_filename to sanitize user uploaded filenames and prevent path traversal attacks
from werkzeug.utils import secure_filename  # Strips harmful characters from uploaded filenames

# Import URLSafeTimedSerializer to generate time-limited, tamper-proof password reset tokens
from itsdangerous import URLSafeTimedSerializer  # Used to create and verify password reset links

# Load environment variables from .env file into os.environ
load_dotenv()  # Reads the .env file if present in the project root directory

# Create the main Flask application instance
app = Flask(__name__)  # Initializes the Flask WSGI application object

# Set the secret key for signing session cookies securely
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-fallback-key-change-me")  # Secret cryptographic key

# Configure application-wide security settings and cookie behaviors
app.config.update(  # Updates the Flask configuration dictionary
    SESSION_COOKIE_HTTPONLY=True,  # Blocks client-side JavaScript from accessing cookies (XSS defense)
    SESSION_COOKIE_SAMESITE="Lax",  # Restricts cookie sending on cross-site requests (CSRF defense)
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",  # Uses HTTPS-only cookies in prod
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # Automatically logs users out after 8 hours of inactivity
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # Limits maximum incoming upload size to 5 megabytes
)  # Finishes setting up security configuration options

# Enable Cross-Site Request Forgery protection across all Flask POST routes
csrf = CSRFProtect(app)  # Validates csrf_token in all submitted HTML forms

# Set up basic logging configuration to output INFO level logs to the console
logging.basicConfig(level=logging.INFO)  # Sets log output threshold to INFO level

# Create a designated logger instance named 'travelworld'
logger = logging.getLogger("travelworld")  # Provides a named logger for tracking app events

# Initialize the token serializer for generating and validating password reset tokens
reset_serializer = URLSafeTimedSerializer(app.secret_key)  # Uses app.secret_key to sign tokens

# Set maximum validity period for password reset tokens to 30 minutes (in seconds)
RESET_TOKEN_MAX_AGE = 30 * 60  # Tokens expire after 1800 seconds (30 minutes)

# Set the maximum allowed failed login attempts before temporarily blocking the user
AUTH_ATTEMPT_LIMIT = 5  # Allows a maximum of 5 consecutive failed login attempts

# Set the duration of the rate-limiting monitoring window to 15 minutes (in seconds)
AUTH_ATTEMPT_WINDOW = 15 * 60  # 900 seconds window for tracking login failures

# Create an in-memory dictionary of queues to store failure timestamps per IP and email
auth_attempts = defaultdict(deque)  # Maps 'ip:email' string to a queue of timestamps

# Define absolute file path for storing user-uploaded package and hotel images
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "image", "uploads")  # Path to /static/image/uploads

# Define set of permitted image file extensions to prevent malicious executable uploads
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}  # Safe image formats only

# Ensure the upload directory exists on the disk, creating it if it doesn't already exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Creates folders recursively without throwing errors

# ─── Helper Functions ────────────────────────────────────────

# Define function to check whether a filename has a safe and permitted image extension
def allowed_image(filename):  # Takes filename string as input
    # Verify dot exists and extension in lowercase is in the allowed set
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS  # Boolean result

# Define function to validate and securely save an uploaded image to disk
def save_uploaded_image(file_storage, prefix):  # Takes file object and name prefix
    # Check if a file was provided and actually has a filename
    if not file_storage or not file_storage.filename:  # If no file uploaded
        return None  # Return None if empty
    # Verify that file has an allowed extension and valid image MIME type
    if not allowed_image(file_storage.filename) or file_storage.mimetype not in {"image/png", "image/jpeg", "image/webp"}:  # Safety check
        flash("Image must be a PNG, JPG or WEBP file.", "error")  # Alert user about invalid format
        return None  # Abort file saving
    # Generate a unique sanitized filename using prefix, random UUID, and original filename
    filename = secure_filename(f"{prefix}_{uuid.uuid4().hex}_{file_storage.filename}")  # Creates collision-safe name
    # Save the file content into the uploads folder on the server
    file_storage.save(os.path.join(UPLOAD_FOLDER, filename))  # Writes file to static/image/uploads/
    # Return the relative path to be saved in the database
    return f"uploads/{filename}"  # Returns relative path for database storage

# Compile regex pattern to validate standard email address format
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # Regex ensuring email has name@domain.tld format

# Define function to check if an email string matches the valid pattern
def is_valid_email(email):  # Takes email string as input
    # Return True if non-empty and regular expression matches
    return bool(email) and bool(EMAIL_RE.match(email.strip()))  # Validates email syntax

# Define function to validate Indian 10-digit mobile phone numbers
def is_valid_phone(phone):  # Takes phone string as input
    # Return True if phone consists purely of 10 digits
    return bool(phone) and phone.strip().isdigit() and len(phone.strip()) == 10  # Checks exactly 10 digits

# Define function to enforce strong password complexity requirements
def is_valid_password(password):  # Takes password string as input
    # Ensure password is a string and contains at least 8 characters
    if not isinstance(password, str) or len(password) < 8:  # Enforces minimum length of 8
        return False  # Rejects weak password
    # Require uppercase, lowercase, digit, and special character
    return all(re.search(p, password) for p in [r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]"])  # Enforces diversity

# Define helper to construct rate-limiting identifier key from IP and email
def auth_attempt_key(email):  # Combines remote client IP and email
    # Returns formatted string 'client_ip:email'
    return f"{request.remote_addr or 'unknown'}:{email.lower()}"  # Unique key for tracking attempts

# Define function to check if an account or IP is currently rate limited
def auth_is_rate_limited(email):  # Checks if failed attempt count exceeded threshold
    now = time.monotonic()  # Current high-resolution monotonic time
    attempts = auth_attempts[auth_attempt_key(email)]  # Queue of previous failure timestamps
    # Evict timestamps older than the 15-minute sliding window
    while attempts and now - attempts[0] > AUTH_ATTEMPT_WINDOW:  # Discard expired timestamps
        attempts.popleft()  # Remove expired entry from left of queue
    # Return True if remaining failures meet or exceed maximum allowed attempts
    return len(attempts) >= AUTH_ATTEMPT_LIMIT  # True if rate limit active

# Define function to record a failed login attempt timestamp
def record_failed_auth(email):  # Called on invalid credentials
    # Append current timestamp to queue for this IP/email combination
    auth_attempts[auth_attempt_key(email)].append(time.monotonic())  # Tracks time of failure

# Define function to clear failed attempts after a successful login
def clear_auth_attempts(email):  # Resets attempt counter on success
    # Remove tracked key from dictionary
    auth_attempts.pop(auth_attempt_key(email), None)  # Clears rate limit queue

# Define function to send automated transactional emails via SMTP
def send_email(recipient, subject, body):  # Takes recipient address, subject line, and body text
    # Fetch SMTP host server and sender address from environment variables
    host, sender = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_FROM")  # Reads SMTP config
    # If SMTP settings are missing, log info and skip sending without crashing
    if not host or not sender:  # Checks if SMTP server is configured
        logger.info("Email not sent (SMTP is not configured): %s", subject)  # Informative log
        return False  # Email not sent
    # Create EmailMessage object to format headers and content
    message = EmailMessage()  # Initializes new message
    message["Subject"], message["From"], message["To"] = subject, sender, recipient  # Sets email headers
    message.set_content(body)  # Sets plain text body content
    # Attempt connecting to SMTP server and transmitting the email
    try:  # Try block to catch network and SMTP errors
        # Connect to SMTP server with 10-second timeout
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as smtp:  # Connects to port 587
            # Upgrade connection to secure TLS if enabled
            if os.environ.get("SMTP_USE_TLS", "true").lower() == "true":  # Checks TLS setting
                smtp.starttls()  # Encrypts connection with TLS
            # Authenticate with SMTP username and password if provided
            if os.environ.get("SMTP_USERNAME"):  # If SMTP credentials provided
                smtp.login(os.environ["SMTP_USERNAME"], os.environ.get("SMTP_PASSWORD", ""))  # Logs into SMTP server
            # Send message to recipient
            smtp.send_message(message)  # Delivers the message
        return True  # Returns True on successful delivery
    except (OSError, smtplib.SMTPException):  # Handles connection failure or auth error
        logger.exception("Unable to send email notification")  # Logs error trace
        return False  # Returns False on failure

# Define function to record an in-app notification in the database and send email
def notify_user(user_id, email, subject, message):  # Dispatches both database alert and email
    # Save notification record into the notifications table in PostgreSQL
    execute("INSERT INTO notifications (user_id,subject,message) VALUES (%s,%s,%s)", (user_id, subject, message))  # Saves in DB
    # Attempt to send an email copy to the user's email address
    send_email(email, subject, message)  # Dispatches email notification

# Define function to log sensitive administrator and customer actions for security auditing
def audit(action, entity_type=None, entity_id=None, details=None):  # Records who did what
    # Determine whether current actor is admin, user, or anonymous guest
    actor_type = "admin" if "admin_id" in session else "user" if "user_id" in session else "anonymous"  # Actor role
    # Retrieve current session user or admin ID
    actor_id = session.get("admin_id") or session.get("user_id")  # Actor primary key
    # Insert audit record into audit_logs table
    execute("""INSERT INTO audit_logs (actor_type,actor_id,action,entity_type,entity_id,details)
               VALUES (%s,%s,%s,%s,%s,%s)""", (actor_type, actor_id, action, entity_type, entity_id, details))  # SQL insert

# Define function to automatically mark approved past bookings as completed
def refresh_expired_bookings():  # Updates status when travel date has passed
    # Update bookings table where travel date is before today
    execute("""UPDATE bookings SET status='Completed'
               WHERE status='Approved' AND travel_date IS NOT NULL AND travel_date < CURRENT_DATE""")  # Auto-complete past trips

# ─── Database Configuration & Query Helpers ─────────────────

# Dictionary holding database connection parameters read from environment or using defaults
DB = dict(  # Database configuration dictionary
    host=os.environ.get("DB_HOST", "localhost"),  # PostgreSQL server host (default: localhost)
    dbname=os.environ.get("DB_NAME", "travelworld"),  # Database name (default: travelworld)
    user=os.environ.get("DB_USER", "postgres"),  # Database username (default: postgres)
    password=os.environ.get("DB_PASSWORD", ""),  # Database password
    port=os.environ.get("DB_PORT", 5432),  # PostgreSQL port (default: 5432)
)  # End of DB config dictionary

# Custom exception class to represent database errors cleanly to user interface
class DatabaseError(Exception):  # Inherits from base Exception
    pass  # Custom error type for catching DB exceptions

# Function to establish and return a new PostgreSQL database connection
def get_db():  # Creates database connection
    # Open connection using dictionary parameters
    conn = psycopg2.connect(**DB)  # Connects to PostgreSQL
    # Enable autocommit so changes are saved immediately without manual commit calls
    conn.autocommit = True  # Sets autocommit mode
    return conn  # Returns active connection object

# Function to execute a SELECT query and fetch records as dictionary objects
def query(sql, params=(), one=False):  # Executes SQL query and returns result
    try:  # Wraps in try-block to catch database errors
        # Open database connection within context manager
        with get_db() as conn:  # Automatically closes connection on exit
            # Create a cursor that returns rows as Python dictionaries
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)  # RealDictCursor gives column name keys
            # Execute SQL statement with parameterized arguments to prevent SQL injection
            cur.execute(sql, params)  # Safely binds parameters
            # Return single row dictionary or list of row dictionaries
            return cur.fetchone() if one else cur.fetchall()  # Fetches 1 row or all rows
    except psycopg2.Error:  # Catches any PostgreSQL driver errors
        logger.exception("Database query failed")  # Logs traceback
        raise DatabaseError("We couldn't complete that request. Please try again.")  # User-friendly exception

# Function to execute INSERT, UPDATE, or DELETE SQL statements
def execute(sql, params=()):  # Executes write/update queries
    try:  # Wraps in try-block
        # Open database connection
        with get_db() as conn:  # Connects to database
            # Create standard database cursor
            cur = conn.cursor()  # Cursor object
            # Execute parameterized SQL query
            cur.execute(sql, params)  # Executes write operation
    except psycopg2.Error:  # Catches SQL errors
        logger.exception("Database write failed")  # Logs error
        raise DatabaseError("We couldn't save that. Please check your input and try again.")  # User-friendly error

# Function to automatically ensure trip_plans table exists in the database
def ensure_trip_plans_table():  # Creates table if not yet present
    # Run DDL statement creating trip_plans table if it doesn't already exist
    execute("""
        CREATE TABLE IF NOT EXISTS trip_plans (
            plan_id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            destination VARCHAR(120) NOT NULL,
            trip_style VARCHAR(50) DEFAULT 'Balanced',
            days INT NOT NULL DEFAULT 1,
            travelers INT NOT NULL DEFAULT 1,
            budget NUMERIC(12,2) DEFAULT 0,
            total_estimate NUMERIC(12,2) DEFAULT 0,
            itinerary_json TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)  # Executes table creation query

# Automatically run table check on module import
try:  # Safe check on startup
    ensure_trip_plans_table()  # Verifies trip_plans table
except Exception as e:  # Ignores if DB connection is unavailable during build
    logger.warning("Trip plans table check skipped or failed on startup: %s", e)  # Log warning

# ─── Error Handlers ──────────────────────────────────────────

# Catch custom DatabaseError exceptions and display friendly error page
@app.errorhandler(DatabaseError)  # Catches DatabaseError
def handle_database_error(err):  # Handles DB exception
    flash(str(err), "error")  # Flashes error message
    return render_template("error.html", message=str(err)), 500  # Returns error template with HTTP 500

# Catch 404 Not Found HTTP errors
@app.errorhandler(404)  # Catches page not found
def handle_not_found(err):  # Handles 404
    return render_template("error.html", message="Page not found."), 404  # Returns 404 template

# Catch unhandled 500 Internal Server Error exceptions
@app.errorhandler(500)  # Catches server crash
def handle_server_error(err):  # Handles 500
    logger.exception("Unhandled server error")  # Logs crash trace
    return render_template("error.html", message="Something went wrong on our end."), 500  # Returns 500 template

# Catch 413 File Too Large errors (uploaded file exceeds 5MB)
@app.errorhandler(413)  # Catches payload too large
def handle_file_too_large(err):  # Handles 413
    return render_template("error.html", message="Image uploads must be 5 MB or smaller."), 413  # Returns 413 error

# Hook executed before every incoming HTTP request
@app.before_request  # Runs before every route call
def maintain_booking_lifecycle():  # Updates booking statuses
    # Ignore static files (css/images/js) to keep performance fast
    if not request.path.startswith("/static/"):  # Only runs for page views
        try:  # Catches unexpected errors
            refresh_expired_bookings()  # Automatically marks past trips as Completed
        except Exception as e:  # Safe catch
            logger.warning(f"Unexpected error refreshing bookings: {e}")  # Logs warning

# Custom Jinja template filter to format numbers as Indian Rupee currency (₹)
@app.template_filter("money")  # Registers 'money' filter for Jinja templates (e.g. {{ price | money }})
def money(value):  # Takes numerical amount
    try:  # Handles valid numeric values
        # Formats float with thousands comma separator and ₹ symbol
        return f"₹{float(value or 0):,.0f}"  # Example: 15000 -> ₹15,000
    except Exception:  # Fallback on parse failure
        return "₹0"  # Returns default ₹0

# ─── Authentication Decorators ───────────────────────────────

# Decorator to protect customer routes that require user login
def login_required(f):  # Decorator function taking route handler
    @wraps(f)  # Preserves function identity and docstring
    def decorated(*args, **kwargs):  # Wrapper function
        # Check if user_id exists in session cookie
        if "user_id" not in session:  # User is not logged in
            flash("Please log in first.", "error")  # Prompt user to sign in
            return redirect(url_for("login"))  # Redirect to login page
        # User is logged in, proceed to route handler
        return f(*args, **kwargs)  # Executes protected view
    return decorated  # Returns decorated function

# Decorator to protect administrative routes that require admin login
def admin_required(f):  # Decorator function taking admin route handler
    @wraps(f)  # Preserves function identity
    def decorated(*args, **kwargs):  # Wrapper function
        # Check if admin_id exists in session cookie
        if "admin_id" not in session:  # Admin is not logged in
            flash("Admin access required.", "error")  # Alert unauthorized access
            return redirect(url_for("admin_login"))  # Redirect to admin login page
        # Admin is verified, proceed to route handler
        return f(*args, **kwargs)  # Executes admin view
    return decorated  # Returns decorated function
