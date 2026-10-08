# DamanCare | ضمان كير

A lightweight Arabic RTL warranty and maintenance tracker built as a full-stack application portfolio project.

## Features
- Add, search, edit and delete devices
- Automatic warranty status and days remaining
- Upload an invoice (PDF or image, max 5 MB)
- Log maintenance dates, descriptions and costs
- Responsive Arabic dashboard
- SQLite relational database with cascading device/repair deletion

## Stack
Python 3.10+, Flask, SQLite, HTML, CSS, Jinja2.

## Quick start
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

The SQLite database and `uploads/` directory are created automatically. The app runs locally; do not deploy publicly without authentication, CSRF protection, production secret management and additional file validation.

## Interview pitch
"I built DamanCare to practice end-to-end application development. It lets users organize device warranties, upload invoices, and record maintenance expenses. I designed the UI, backend routes and relational database, including CRUD operations and automatic warranty calculations."

## Future improvements
User accounts, reminders, OCR invoice extraction, PostgreSQL and automated tests.
