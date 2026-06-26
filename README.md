# 🏥 MedAI GH — AI-Powered Pharmacy Inventory Management System

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)
![Node.js](https://img.shields.io/badge/Node.js-18%2B-brightgreen.svg)
![License](https://img.shields.io/badge/license-ISC-orange.svg)
![Status](https://img.shields.io/badge/status-Production%20Ready-success.svg)

> **MedAI GH** is a full-stack, AI-powered pharmacy inventory management system designed for Ghanaian healthcare institutions. It combines a machine learning demand forecasting engine with a real-time inventory platform, offering pharmacists and administrators an intelligent, data-driven tool to manage medicines, track expiry risks, process dispensing transactions, and maintain full audit compliance.
> 
> **Version 1.1 Update:** The system is now **100% Air-Gapped and Offline**. All databases, CDNs, and ML engines run entirely locally to ensure maximum data privacy and resilience against internet outages.

---

## 📋 Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Application](#running-the-application)
- [Default Credentials](#default-credentials)
- [API Reference](#api-reference)
- [Machine Learning Model](#machine-learning-model)
- [Modules & Pages](#modules--pages)
- [Database Design](#database-design)
- [Contributing](#contributing)

---

## ✨ Features

### 🤖 AI & Machine Learning
- **Demand Forecasting** — Random Forest Regressor predicts daily drug consumption rates from historical sales data
- **Automated Expiry Risk Classifier** — Dynamically categorizes medicines into `High Risk`, `Medium Risk`, and `Low Risk` based on configurable expiry thresholds
- **Stock Exhaust Prediction** — Calculates predicted stockout dates using ML-estimated consumption rates

### 📦 Inventory Management
- Real-time inventory tracking with search and filtering
- Batch-level tracking (Batch ID, Manufacturer, Manufacturing Date, Expiry Date)
- Auto-reorder alert system with configurable reorder levels
- Support for 500+ medicine records seeded from a curated dataset

### 💊 Point-of-Sale (POS) & Dispensing
- Pharmacist-facing POS terminal for medicine dispensing
- Cart management with quantity validation against live stock
- Customer name tracking and transaction receipts
- Automatic stock deduction on checkout

### 🔄 Refund Management
- Pharmacist-driven refund requests tied to specific recent transactions
- Admin approval workflow for requested refunds
- Automatic audit tracking for all financial adjustments

### 📊 Reporting & Analytics
- Sales reports (daily, all-time, per-pharmacist)
- Risk distribution charts by medicine category
- Admin dashboard with KPIs: total items, stock value, low-stock alerts, expiry risks

### 🔐 Security & Audit
- Role-based access control: `admin` and `pharmacist` roles
- Complete audit trail — every login, dispensing event, refund, and settings change is logged
- System-level audit log viewer for administrators
- 100% Offline execution with zero external CDN dependencies

### ⚙️ System Administration
- Staff management: create, edit, and delete user accounts with local avatar generation
- Configurable system settings: hospital name, NHIS ID, currency, expiry threshold

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (100% Offline, no external CDNs) |
| **Backend API** | Python, Flask, Waitress (Local Production Server) |
| **Database** | SQLite3 (Embedded, completely offline) |
| **Machine Learning** | scikit-learn (Random Forest), pandas, joblib |
| **Package Manager** | npm (Node scripts), pip (Python) |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (Frontend)                │
│   login.html │ index.html │ inventory.html │ pos.html│
│   pharmacist.html │ reports.html │ refunds.html     │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP / REST API (Local)
          ┌───────────┴────────────┐
          │                        │
          │  Python Flask API      │
          │  (app.py / api/index)  │
          │  + Local ML Engine     │
          │  Port: 5000            │
          │                        │
          └───────────┬────────────┘
                      │
          ┌───────────▼────────────┐
          │     SQLite3 (Local)    │
          │     medai.db           │
          └────────────────────────┘
```

---

## 📁 Project Structure

```
AI-Based/
│
├── 📂 api/                     # Backend API handlers
│   └── index.py                # Core Flask API & routing logic
│
├── 📂 public/                  # Frontend static files (100% Offline Assets)
│   ├── 📂 css/
│   │   └── style.css           # Global stylesheet
│   ├── 📂 js/                  # Frontend JavaScript modules
│   ├── 📂 vendor/              # Local dependencies (Chart.js, JsBarcode, FontAwesome)
│   ├── index.html              # Admin Dashboard
│   ├── login.html              # Login Page
│   ├── inventory.html          # Inventory Management
│   ├── pos.html                # Point-of-Sale Terminal
│   ├── pharmacist.html         # Pharmacist Portal
│   ├── forecasting.html        # Demand Forecasting View
│   ├── reports.html            # Sales Reports
│   ├── audit.html              # Audit Log Viewer
│   ├── settings.html           # System Settings
│   ├── refunds.html            # Refund Management
│   └── users.html              # Staff Management
│
├── app.py                      # Python Waitress production server wrapper
├── ml_model.py                 # ML Intelligence Layer (Random Forest)
├── seed_db.py                  # Database SQLite seeding script
│
├── 📊 Data & Models
│   ├── project dataset.csv     # Source dataset (~500+ medicine records)
│   ├── model.pkl               # Pre-trained Random Forest model
│   └── encoder.pkl             # Category Label Encoder
│
├── medai.db                    # Master SQLite Database (Auto-generated)
├── package.json                # Node.js npm wrapper scripts
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## 🚀 Getting Started

### Prerequisites

Ensure the following are installed on your machine:

- **Node.js** v18 or higher (Used for script wrapping) — [Download](https://nodejs.org/)
- **Python** 3.9 or higher — [Download](https://python.org/)

---

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/your-username/AI-Based.git
cd AI-Based
```

**2. Install Node dependencies (for runner scripts)**
```bash
npm install
```

**3. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**4. Initialize the Database**
If the `medai.db` file does not exist, the system will automatically create it and seed it with the default users and inventory from `project dataset.csv` when you first run the app. You can also seed it manually:
```bash
python seed_db.py
```

---

### Running the Application

This launches the Flask-based server via Waitress (a production-quality WSGI server) which natively hosts the ML models and serves the static files locally.

```bash
npm start
```
*(This is a wrapper for `python app.py`)*

The application will be securely available at: **http://localhost:5000**

---

## 🔑 Default Credentials

> ⚠️ **Change these credentials immediately after first login.**

| Role | Username | Password | Access Level |
|---|---|---|---|
| Administrator | `sheripha` | `admin123` | Full system access |
| Pharmacist | `pharm` | `pharm123` | POS, inventory view, personal sales, refunds |

---

## 📡 API Reference (Local)

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/login` | Authenticate user, returns role |
| `POST` | `/api/logout` | Log session end to audit trail |

### Dashboard & Inventory
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/dashboard` | KPI summary (totals, risk counts) |
| `GET` | `/api/inventory` | Full inventory list (supports `?search=`) |
| `GET` | `/api/recommendations` | Top 10 high-risk medicine alerts |
| `GET` | `/api/forecast` | Demand forecast data with stockout dates |
| `GET` | `/api/charts/risk` | Category stock distribution data |

### Sales, Refunds & POS
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/checkout` | Process a dispensing transaction |
| `GET` | `/api/sales/today` | Today's revenue and transaction count |
| `GET` | `/api/my/sales` | Pharmacist's personal sales history |
| `GET/POST`| `/api/refunds` | Fetch or submit a refund request |
| `PUT` | `/api/refunds/<id>` | Admin approval/rejection of refund |

### Admin — Reporting & Audit
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/sales` | All sales records |
| `GET` | `/api/system-audit` | Full system audit log |
| `GET` | `/api/users` | List all staff accounts |
| `POST` | `/api/admin/users` | Create, edit, or delete a user (`action` field) |
| `GET/POST`| `/api/settings` | Retrieve or update system settings |

---

## 🧠 Machine Learning Model

The `PharmacyIntelligenceLayer` class in `ml_model.py` powers the AI engine offline.

### Algorithm
**Random Forest Regressor** (`scikit-learn`) with 100 estimators.

### Features Used for Training
| Feature | Description |
|---|---|
| `Unit_Cost_USD` | Cost price of the medicine |
| `Category_Encoded` | Label-encoded medicine category |
| `Sales_Last_30_Days` | Historical sales volume |

### Target Variable
- `Daily_Consumption_Rate` — Predicted units consumed per day

> The model is **pre-trained and saved to disk** (`model.pkl`). It loads automatically on server start directly into your local RAM without requiring external APIs.

---

## 🗄️ Database Design

The system runs entirely on **SQLite3** (`medai.db`), requiring zero database servers or cloud infrastructure.

### Core Tables
1. **`users`** — Staff accounts, roles, and hashed credentials.
2. **`inventory`** — Live stock data, batch numbers, and ML predicted expiry dates.
3. **`settings`** — Global configuration parameters (currency, hospital name).
4. **`audit`** — Immutable logs of every system action.
5. **`sales`** — History of POS transactions.
6. **`refunds`** — Log of requested and processed refunds tied to sales.

---

## 👥 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

---

## 📞 Support

For issues, bugs, or feature requests, please open an issue on the GitHub repository.

---

> **MedAI GH** — *Intelligent Pharmacy Management for Modern Healthcare.*
> Built with ❤️ for the Ghanaian healthcare ecosystem.
