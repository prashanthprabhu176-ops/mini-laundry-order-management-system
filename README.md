# Mini Laundry Order Management System

A lightweight dry cleaning order-management system built for the "AI-First" assignment. It includes:

- Order creation with automatic bill calculation and unique order IDs
- Order status tracking across `RECEIVED`, `PROCESSING`, `READY`, and `DELIVERED`
- Order listing with filters for status, customer name, phone, and garment type
- Dashboard metrics for total orders, total revenue, and orders per status
- A simple browser UI and a Postman collection for demoing the APIs

## Tech Stack

- Backend: Python 3 standard library (`http.server`, `sqlite3`, `json`)
- Storage: SQLite
- Frontend: Plain HTML, CSS, and JavaScript
- Dependencies: None

## Features Implemented

### Core Features

- Create an order with:
  - Customer name
  - Phone number
  - Multiple garment items
  - Quantity per item
  - Auto-filled price per item based on garment type
- Generate:
  - Total bill amount
  - Unique order ID
- Update order status
- View all orders sorted by newest first
- Filter by:
  - Status
  - Customer name / phone
- Basic dashboard:
  - Total orders
  - Total revenue
  - Orders per status
- Validation:
  - Phone number must be exactly 10 digits
  - At least one garment item is required
  - Quantity must be greater than zero

### Bonus Features

- Simple frontend UI
- SQLite persistence instead of in-memory storage
- Search by garment type
- Estimated delivery date
- Smart garment pricing with rate-card based auto-fill
- Status color coding and quick action buttons
- Total item count per order
- Postman collection for API testing

## Project Structure

```text
.
|-- app.py
|-- static/
|   |-- index.html
|   |-- styles.css
|   `-- app.js
|-- postman/
|   `-- Mini-Laundry-Order-Management.postman_collection.json
`-- README.md
```

## Setup Instructions

### Prerequisites

- Python 3.10+ (tested with Python 3.14)

### Run Locally

1. Open the project folder.
2. Start the app:

```bash
python3 app.py
```

3. Open the UI:

```text
http://127.0.0.1:8000
```

The SQLite database is created automatically inside `data/laundry.db`.

## API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/config` | Supported statuses + default garment pricing |
| `POST` | `/api/orders` | Create a new order |
| `GET` | `/api/orders` | List/filter orders |
| `GET` | `/api/orders/{orderId}` | Get one order |
| `PATCH` | `/api/orders/{orderId}/status` | Update order status |
| `GET` | `/api/dashboard` | Dashboard summary |

### Example Create Order Payload

```json
{
  "customer_name": "Ananya Rao",
  "phone": "9876543210",
  "estimated_delivery": "2026-04-18",
  "items": [
    {
      "garment_type": "Shirt",
      "quantity": 2,
      "unit_price": 50
    },
    {
      "garment_type": "Saree",
      "quantity": 1,
      "unit_price": 180
    }
  ]
}
```

## Demo Options

### Option 1: Browser UI

- Use the app at `http://127.0.0.1:8000`
- Create orders, filter them, and update statuses directly from the UI

### Option 2: Postman

- Import `postman/Mini-Laundry-Order-Management.postman_collection.json`
- Set `baseUrl` to `http://127.0.0.1:8000`
- Create an order, copy the returned `order_id`, and paste it into the `orderId` variable for status updates

## AI Usage Report

### Tools Used

- OpenAI Codex / ChatGPT-style prompting for system design, scaffolding, UI generation, and documentation

### How AI Helped

- Helped choose a fast stack with no external dependencies
- Scaffolded the Python API shape and data model
- Generated the single-page frontend structure quickly
- Helped draft README sections and demo assets
- Accelerated iteration on validation, filtering, and status flow

### Representative Prompts Used

1. `Build a mini laundry order management system using Python standard library + SQLite. Keep it simple, add REST endpoints for order creation, listing, filtering, status updates, and dashboard metrics.`
2. `Generate a minimal but polished single-page UI to create laundry orders, preview billing, list orders, filter by status or customer, and update status inline.`
3. `Draft a README for an AI-first assignment. Include setup instructions, features implemented, AI usage report, tradeoffs, and how to demo the project.`

### What AI Got Wrong or Incomplete

- Initial generated code leaned toward framework-heavy solutions, which would have required package installs and more setup time
- Some early UI ideas were too generic and not tailored to a quick assignment demo
- Validation details such as garment-item checks, pricing fallbacks, and friendly error messages needed tightening
- The assignment explicitly asked for AI usage transparency, so the README had to be made more honest and specific instead of sounding generic

### What I Improved Manually

- Switched to a zero-dependency implementation to reduce setup friction
- Added SQLite persistence instead of only in-memory storage
- Tightened validation for empty names, phones, quantities, prices, and unsupported garment types
- Added explicit 10-digit phone validation and stronger guardrails for garment entries
- Added garment-type filtering and estimated delivery support
- Reworked the frontend to be cleaner and more demo-friendly
- Replaced the dropdown-only status control with faster row actions and colored status badges
- Added a Postman collection and clearer reviewer instructions

## Tradeoffs

- No authentication was added to keep the build focused on the assignment scope
- No deployment was done in this environment
- No pagination or advanced reporting was added because the goal was speed and practical completeness
- The standard-library HTTP server is perfect for a demo assignment, but not enough for production hardening, auth, rate limits, or concurrent scaling

## What I Would Improve With More Time

- Deploy to Render or Railway
- Add login/auth for staff users
- Add edit/delete order flows
- Add payment status and customer history
- Add automated tests and seed data
- Add charts for dashboard reporting
- Add export/download reports

## Publishing to GitHub

This environment did not publish directly to GitHub, but the project is ready to push:

```bash
git init
git add .
git commit -m "Build mini laundry order management system"
git branch -M main
git remote add origin <your-public-github-repo-url>
git push -u origin main
```
