# TravelWorld — Tourism Management System

TravelWorld is a full-stack Flask and PostgreSQL application for discovering tour packages, making bookings, simulating payments, and managing travel operations through an admin panel.

## Placement-ready highlights

- Secure user and admin login with hashed passwords, CSRF protection, secure session cookies, upload limits, and login rate limiting.
- Package search, booking, hotel/transport selection, payment tracking, transaction IDs, printable receipts, and cancellation flow.
- Booking lifecycle: `Pending → Approved → Completed` or `Cancelled`.
- Verified travelers can submit and update one review per completed/approved booking.
- In-app notifications plus SMTP-ready email notifications for reset, payment, and booking events.
- Admin analytics, revenue chart, searchable/filterable/paginated bookings, and package/hotel/transport/report management.
- Deployment files for Render and automated smoke tests.

## Local setup

1. Create and activate a virtual environment, then install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set the database values. Use a long random `SECRET_KEY` outside local development.

3. Create PostgreSQL database and load the schema:

   ```powershell
   createdb travelworld
   psql -U postgres -d travelworld -f schema.sql
   ```

   Re-run `schema.sql` after pulling changes; its migrations add the newer tables and columns safely.

4. Start the application:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

   Open http://localhost:5000.

Default admin account for a fresh database:

- Email: `admin@travelworld.com`
- Password: `admin123`

Change this password before deploying.

## Email configuration

SMTP is optional. Without it, password-reset links appear in the app for local demo use. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` in `.env` to send real email notifications. Never commit `.env`.

## Tests

Run the smoke tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Deploying on Render

`render.yaml` and `Procfile` are included. Push this repository to GitHub, create a Render Blueprint from the repository, then add `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_PORT` as environment variables. Use a managed PostgreSQL instance and set `COOKIE_SECURE=true` in production.

## Resume description

> Built and deployed a full-stack Tourism Management System using Flask, PostgreSQL, Jinja2, and secure session-based authentication. Implemented booking lifecycle management, reviews, simulated payments with receipts, admin analytics, role-based operations, email-ready notifications, and automated tests.

README.md: This is just a text file used to write notes, instructions, or a description of your project. If you were sharing your code on GitHub, this would be the "homepage" text people read. If you already know how your project works and don't need the notes, you can delete it.
.gitignore: This is a configuration file for Git (a tool used to save versions of your code and upload to GitHub). It tells Git to ignore certain secret or junk files (like your database passwords or __pycache__ folders). If you aren't using Git or GitHub to save your code, this file does absolutely nothing and can be deleted.