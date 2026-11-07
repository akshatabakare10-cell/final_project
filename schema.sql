-- =============================================================
-- TravelWorld Database Schema
-- Defines all relational tables, constraints, foreign keys, and indexes.
-- Execution command: psql -U postgres -d travelworld -f schema.sql
-- =============================================================

-- Create users table to store customer accounts and authentication data
CREATE TABLE IF NOT EXISTS users (  -- Creates users table if it does not already exist
    user_id     SERIAL PRIMARY KEY,  -- Auto-incrementing unique identifier for each registered user
    full_name   VARCHAR(120) NOT NULL,  -- Customer's real full name; required for bookings and tickets
    email       VARCHAR(120) UNIQUE NOT NULL,  -- Unique login email; prevents duplicate accounts
    phone       VARCHAR(10) NOT NULL,  -- 10-digit mobile number for SMS and booking contact
    password    VARCHAR(200) NOT NULL,  -- Securely hashed password string (never stored in plaintext)
    avatar_filename VARCHAR(255),  -- Path to user's uploaded profile picture inside static uploads
    created_at  TIMESTAMP DEFAULT NOW(),  -- Timestamp when the account was first created
    updated_at  TIMESTAMP DEFAULT NOW()  -- Timestamp of last profile or password modification
);  -- End of users table definition

-- Create admins table to store administrative staff accounts with elevated privileges
CREATE TABLE IF NOT EXISTS admins (  -- Creates admins table if it does not already exist
    admin_id    SERIAL PRIMARY KEY,  -- Unique identifier for the administrator account
    full_name   VARCHAR(120) NOT NULL,  -- Full name of the administrator staff member
    email       VARCHAR(120) UNIQUE NOT NULL,  -- Unique administrator login email
    password    VARCHAR(200) NOT NULL  -- Hashed administrator password
);  -- End of admins table definition

-- Create hotels table to store accommodation options that can be included in tour packages
CREATE TABLE IF NOT EXISTS hotels (  -- Creates hotels table if it does not already exist
    hotel_id         SERIAL PRIMARY KEY,  -- Unique identifier for the hotel property
    hotel_name       VARCHAR(150) NOT NULL,  -- Name of hotel or resort (e.g. 'Seaside Luxury Resort')
    destination_name VARCHAR(120),  -- City or tourist location where hotel is situated (e.g. 'Goa')
    room_type        VARCHAR(60) DEFAULT 'Deluxe',  -- Category of room (Deluxe, Suite, Standard, Villa)
    price_per_night  NUMERIC(10,2) NOT NULL,  -- Base nightly rate in Indian Rupees (₹)
    rating           INT CHECK (rating BETWEEN 1 AND 5),  -- Star rating constrained between 1 and 5
    availability     VARCHAR(20) DEFAULT 'Available',  -- Availability status (Available or Sold Out)
    image_filename   VARCHAR(255),  -- Relative file path to hotel promotional image
    created_at       TIMESTAMP DEFAULT NOW()  -- Timestamp when the hotel was added
);  -- End of hotels table definition

-- Create transport table to store travel vehicle options (flights, trains, private cabs)
CREATE TABLE IF NOT EXISTS transport (  -- Creates transport table if it does not already exist
    transport_id      SERIAL PRIMARY KEY,  -- Unique identifier for the transport option
    mode              VARCHAR(60) NOT NULL,  -- Transport category (Flight, Train, Car Rental, Airport Pickup)
    transport_type    VARCHAR(80),  -- Specific sub-type (e.g. 'Non-stop Flight', 'AC Sleeper Train')
    vehicle_name      VARCHAR(100),  -- Carrier or vehicle name (e.g. 'IndiGo 6E-204', 'Innova Crysta')
    source_name       VARCHAR(120),  -- Departure origin city or location
    destination_name  VARCHAR(120),  -- Arrival destination city or location
    airport_name      VARCHAR(120),  -- Airport or railway station name
    price             NUMERIC(10,2) NOT NULL,  -- Fare per passenger in Indian Rupees (₹)
    created_at        TIMESTAMP DEFAULT NOW()  -- Timestamp when the transport option was recorded
);  -- End of transport table definition

-- Create packages table to store curated vacation packages
CREATE TABLE IF NOT EXISTS packages (  -- Creates packages table if it does not already exist
    package_id       SERIAL PRIMARY KEY,  -- Unique identifier for each holiday package
    package_name     VARCHAR(150) NOT NULL,  -- Marketing title of the tour (e.g. 'Goa Beach Paradise')
    destination_name VARCHAR(120),  -- Main tourist destination featured in the trip
    description      TEXT,  -- Long-form overview describing tour attractions and highlights
    duration         VARCHAR(80),  -- Trip duration summary (e.g. '4 Days / 3 Nights')
    travelers_limit  INT DEFAULT 4,  -- Maximum group size permitted for this package
    seats_available  INT,  -- Real-time count of available remaining seats
    start_date       DATE,  -- Departure calendar date (NULL if flexible evergreen tour)
    price            NUMERIC(10,2) NOT NULL,  -- Base cost per traveler in Indian Rupees (₹)
    hotel_id         INT REFERENCES hotels(hotel_id),  -- Foreign key linking default hotel accommodation
    transport_id     INT REFERENCES transport(transport_id),  -- Foreign key linking default transportation
    image_filename   VARCHAR(255),  -- Path to package banner photo
    created_at       TIMESTAMP DEFAULT NOW()  -- Timestamp when the tour package was published
);  -- End of packages table definition

-- Create bookings table to store customer reservations for vacation packages
CREATE TABLE IF NOT EXISTS bookings (  -- Creates bookings table if it does not already exist
    booking_id          SERIAL PRIMARY KEY,  -- Unique reservation confirmation ID
    user_id             INT REFERENCES users(user_id),  -- Foreign key identifying the customer who booked
    package_id          INT REFERENCES packages(package_id),  -- Foreign key identifying the booked package
    travel_date         DATE,  -- Chosen calendar date of travel
    travelers           INT DEFAULT 1,  -- Number of travelers in the booking party
    total_price         NUMERIC(10,2),  -- Total package reservation cost (price * travelers)
    status              VARCHAR(30) DEFAULT 'Pending',  -- Reservation workflow status: Pending, Approved, Completed, Cancelled
    coupon_id           INT,  -- Optional foreign key referencing applied discount coupon
    discount_amount     NUMERIC(10,2) DEFAULT 0,  -- Monetary discount applied to order
    cancelled_at        TIMESTAMP,  -- Timestamp when booking was cancelled (if applicable)
    cancellation_reason VARCHAR(500),  -- Explanation for cancellation submitted by user or admin
    booking_date        TIMESTAMP DEFAULT NOW()  -- Timestamp when booking was initiated
);  -- End of bookings table definition

-- Create hotel_bookings table to store hotel add-on details chosen by customer during booking
CREATE TABLE IF NOT EXISTS hotel_bookings (  -- Creates hotel_bookings table if it does not already exist
    hotel_booking_id SERIAL PRIMARY KEY,  -- Unique hotel reservation record ID
    user_id          INT REFERENCES users(user_id),  -- Foreign key identifying customer
    booking_id       INT REFERENCES bookings(booking_id),  -- Foreign key linking to parent package booking
    hotel_id         INT REFERENCES hotels(hotel_id),  -- Foreign key identifying selected hotel
    full_name        VARCHAR(120),  -- Primary guest name registered at hotel reception
    email            VARCHAR(120),  -- Guest email for hotel voucher delivery
    checkin          DATE,  -- Check-in calendar date
    checkout         DATE,  -- Check-out calendar date
    room_type        VARCHAR(60),  -- Room tier selected (Deluxe, Suite, etc.)
    total_price      NUMERIC(10,2),  -- Total accommodation charge (price_per_night * nights)
    created_at       TIMESTAMP DEFAULT NOW()  -- Timestamp when hotel selection was saved
);  -- End of hotel_bookings table definition

-- Create transport_bookings table to store flight/cab/train transit add-ons for a booking
CREATE TABLE IF NOT EXISTS transport_bookings (  -- Creates transport_bookings table if it does not already exist
    transport_booking_id SERIAL PRIMARY KEY,  -- Unique transport reservation record ID
    user_id              INT REFERENCES users(user_id),  -- Foreign key identifying traveler
    booking_id           INT REFERENCES bookings(booking_id),  -- Foreign key linking to parent package booking
    transport_id         INT REFERENCES transport(transport_id),  -- Foreign key identifying transport option
    mode                 VARCHAR(60),  -- Transit mode (Flight, Train, Cab)
    from_location        VARCHAR(120),  -- Departure pickup address or station
    to_location          VARCHAR(120),  -- Dropoff destination address
    airport_name         VARCHAR(120),  -- Airport terminal or station name
    travel_date          DATE,  -- Travel departure date
    pickup_date          DATE,  -- Cab pickup date
    pickup_time          TIME,  -- Exact pickup clock time
    return_date          DATE,  -- Return trip date if round-trip
    passengers           INT DEFAULT 1,  -- Passenger headcount
    travel_class         VARCHAR(40),  -- Travel cabin class (Economy, Business, AC Tier 1)
    total_price          NUMERIC(10,2),  -- Total transit cost
    created_at           TIMESTAMP DEFAULT NOW()  -- Timestamp when transport was saved
);  -- End of transport_bookings table definition

-- Create payments table to store financial transactions, receipts, and payment status
CREATE TABLE IF NOT EXISTS payments (  -- Creates payments table if it does not already exist
    payment_id      SERIAL PRIMARY KEY,  -- Unique invoice payment receipt ID
    user_id         INT REFERENCES users(user_id),  -- Foreign key identifying payer
    booking_id      INT REFERENCES bookings(booking_id),  -- Foreign key linking to paid booking
    amount          NUMERIC(10,2) NOT NULL,  -- Amount paid in Indian Rupees (₹)
    payment_method  VARCHAR(40),  -- Payment gateway channel (card, upi, bank, cash)
    transaction_id  VARCHAR(80),  -- External reference code (e.g. 'TW-20260909-ABCD1234')
    status          VARCHAR(20) DEFAULT 'Paid',  -- Transaction status (Paid, Refunded, Failed)
    payment_date    TIMESTAMP DEFAULT NOW()  -- Exact timestamp when payment was completed
);  -- End of payments table definition

-- Create user_reports table to handle customer support tickets and issue reporting
CREATE TABLE IF NOT EXISTS user_reports (  -- Creates user_reports table if it does not already exist
    report_id      SERIAL PRIMARY KEY,  -- Unique support ticket ID
    user_id        INT REFERENCES users(user_id),  -- Foreign key identifying customer seeking help
    service_type   VARCHAR(40),  -- Affected service category (Hotel, Transport, Package, Payment)
    reference_id   INT,  -- Optional reference number (such as booking_id)
    subject        VARCHAR(200),  -- Brief summary title of customer issue
    message        TEXT,  -- Detailed description of the problem or complaint
    status         VARCHAR(30) DEFAULT 'Open',  -- Ticket progress: Open, In Progress, Resolved
    created_at     TIMESTAMP DEFAULT NOW()  -- Timestamp when ticket was submitted
);  -- End of user_reports table definition

-- Create package_reviews table to store verified traveler ratings and testimonials
CREATE TABLE IF NOT EXISTS package_reviews (  -- Creates package_reviews table if it does not already exist
    review_id    SERIAL PRIMARY KEY,  -- Unique review identifier
    user_id      INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- Customer who wrote review
    package_id   INT NOT NULL REFERENCES packages(package_id) ON DELETE CASCADE,  -- Package reviewed
    booking_id   INT NOT NULL REFERENCES bookings(booking_id) ON DELETE CASCADE,  -- Verified booking proof
    rating       INT NOT NULL CHECK (rating BETWEEN 1 AND 5),  -- Star rating constrained from 1 to 5
    comment      VARCHAR(1000) NOT NULL,  -- Customer review narrative (up to 1,000 characters)
    created_at   TIMESTAMP DEFAULT NOW(),  -- Timestamp when review was posted
    updated_at   TIMESTAMP DEFAULT NOW(),  -- Timestamp when review was edited
    UNIQUE (user_id, booking_id)  -- Ensures each customer can only review a booking once
);  -- End of package_reviews table definition

-- Create notifications table to deliver in-app notifications and alerts to travelers
CREATE TABLE IF NOT EXISTS notifications (  -- Creates notifications table if it does not already exist
    notification_id SERIAL PRIMARY KEY,  -- Unique notification identifier
    user_id         INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- Recipient customer ID
    subject         VARCHAR(200) NOT NULL,  -- Alert heading (e.g. 'Booking Approved')
    message         TEXT NOT NULL,  -- Body text of the notification
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,  -- Unread indicator (turns true once seen)
    created_at      TIMESTAMP DEFAULT NOW()  -- Timestamp when notification was sent
);  -- End of notifications table definition

-- Create wishlists table to allow customers to bookmark and save favorite packages
CREATE TABLE IF NOT EXISTS wishlists (  -- Creates wishlists table if it does not already exist
    wishlist_id SERIAL PRIMARY KEY,  -- Unique bookmark ID
    user_id     INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- Customer who saved package
    package_id  INT NOT NULL REFERENCES packages(package_id) ON DELETE CASCADE,  -- Saved package ID
    created_at  TIMESTAMP DEFAULT NOW(),  -- Timestamp when bookmarked
    UNIQUE(user_id, package_id)  -- Prevents adding duplicate wishlist entries
);  -- End of wishlists table definition

-- Create coupons table to store promotional discount promo codes
CREATE TABLE IF NOT EXISTS coupons (  -- Creates coupons table if it does not already exist
    coupon_id      SERIAL PRIMARY KEY,  -- Unique coupon ID
    code           VARCHAR(30) UNIQUE NOT NULL,  -- Promo code entered at checkout (e.g. 'WELCOME10')
    discount_type  VARCHAR(10) NOT NULL CHECK (discount_type IN ('Percent','Fixed')),  -- 'Percent' or 'Fixed' discount
    discount_value NUMERIC(10,2) NOT NULL CHECK (discount_value > 0),  -- Discount value (e.g. 10% or ₹500)
    minimum_amount NUMERIC(10,2) DEFAULT 0,  -- Minimum cart value required to unlock discount
    expires_at     DATE,  -- Expiration calendar date
    usage_limit    INT,  -- Maximum total redemptions permitted across platform
    times_used     INT DEFAULT 0,  -- Current redemption counter
    is_active      BOOLEAN DEFAULT TRUE,  -- Active coupon toggle switch
    created_at     TIMESTAMP DEFAULT NOW()  -- Timestamp when coupon was created
);  -- End of coupons table definition

-- Create audit_logs table to record sensitive operations for security and compliance
CREATE TABLE IF NOT EXISTS audit_logs (  -- Creates audit_logs table if it does not already exist
    audit_id    SERIAL PRIMARY KEY,  -- Unique audit event ID
    actor_type  VARCHAR(20) NOT NULL,  -- Role of person performing action (admin, user, anonymous)
    actor_id    INT,  -- ID of user or admin
    action      VARCHAR(120) NOT NULL,  -- Name of event (e.g. 'profile_updated', 'payment_received')
    entity_type VARCHAR(50),  -- Targeted table entity (e.g. 'package', 'booking')
    entity_id   INT,  -- Primary key of affected record
    details     TEXT,  -- Additional metadata or transaction ID
    created_at  TIMESTAMP DEFAULT NOW()  -- Precise timestamp when event occurred
);  -- End of audit_logs table definition

-- Create trip_plans table to store custom itineraries created via the interactive Trip Planner
CREATE TABLE IF NOT EXISTS trip_plans (  -- Creates trip_plans table if it does not already exist
    plan_id        SERIAL PRIMARY KEY,  -- Unique trip plan identifier
    user_id        INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- Customer who designed plan
    destination    VARCHAR(120) NOT NULL,  -- Planned travel destination
    trip_style     VARCHAR(50) DEFAULT 'Balanced',  -- Travel style (Adventure, Luxury, Relax, Family, Balanced)
    days           INT NOT NULL DEFAULT 1,  -- Duration of trip in days
    travelers      INT NOT NULL DEFAULT 1,  -- Number of traveling companions
    budget         NUMERIC(12,2) DEFAULT 0,  -- Budget limit specified by user
    total_estimate NUMERIC(12,2) DEFAULT 0,  -- Calculated total estimated expense
    itinerary_json TEXT,  -- Full day-by-day itinerary serialized as JSON text
    created_at     TIMESTAMP DEFAULT NOW()  -- Timestamp when plan was saved
);  -- End of trip_plans table definition

-- =============================================================
-- Performance Optimization Indexes
-- Accelerates SQL JOINs and filtered WHERE searches across tables
-- =============================================================

CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);  -- Speeds up customer booking dashboard queries
CREATE INDEX IF NOT EXISTS idx_bookings_package_id ON bookings(package_id);  -- Speeds up package booking counts
CREATE INDEX IF NOT EXISTS idx_hotel_bookings_booking_id ON hotel_bookings(booking_id);  -- Speeds up hotel addon lookups
CREATE INDEX IF NOT EXISTS idx_transport_bookings_booking_id ON transport_bookings(booking_id);  -- Speeds up transport addon lookups
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);  -- Speeds up payment history queries
CREATE INDEX IF NOT EXISTS idx_payments_booking_id ON payments(booking_id);  -- Speeds up invoice receipt retrieval
CREATE INDEX IF NOT EXISTS idx_user_reports_user_id ON user_reports(user_id);  -- Speeds up support ticket lookups
CREATE INDEX IF NOT EXISTS idx_packages_destination ON packages(destination_name);  -- Speeds up search queries by destination
CREATE INDEX IF NOT EXISTS idx_reviews_package_id ON package_reviews(package_id);  -- Speeds up reviews loading on package page
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id, is_read, created_at DESC);  -- Speeds up notification badge lookups
CREATE INDEX IF NOT EXISTS idx_wishlists_user_id ON wishlists(user_id);  -- Speeds up user wishlist display
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);  -- Speeds up admin audit log reviews

-- =============================================================
-- Initial Seed Data
-- Creates default administrator account and promotional welcome coupon
-- =============================================================

-- Seed default administrator account with pre-hashed scrypt password ('admin123')
INSERT INTO admins (full_name, email, password)  -- Inserts default admin account
VALUES ('Admin', 'admin@travelworld.com',  -- Default admin credentials
        'scrypt:32768:8:1$ldrhDbRCbHa7ASGa$7e1dcaa0e131ecc7da171ebdbb39a612e19c48460ab90a6c39300ceaec1067df13b37e889c872dc1a9d714c02eeb9532d4b3c347f5ccbe4db2cc0d8230e30ea5')  -- Password hash for 'admin123'
ON CONFLICT (email) DO NOTHING;  -- Prevents errors if admin account already exists

-- Seed default promotional 10% welcome coupon code
INSERT INTO coupons (code, discount_type, discount_value, minimum_amount, usage_limit)  -- Inserts initial discount coupon
VALUES ('WELCOME10', 'Percent', 10, 1000, 100)  -- 10% off for orders above ₹1,000, limited to 100 uses
ON CONFLICT (code) DO NOTHING;  -- Prevents duplicate errors if coupon exists
