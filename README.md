# 🏥 MedAI GH — AI-Powered Pharmacy Inventory Management System

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)
![Node.js](https://img.shields.io/badge/Node.js-18%2B-brightgreen.svg)
![License](https://img.shields.io/badge/license-ISC-orange.svg)
![Status](https://img.shields.io/badge/status-Production%20Ready-success.svg)

> **MedAI GH** is a full-stack, AI-powered pharmacy inventory management system designed for Ghanaian healthcare institutions. It combines a machine learning demand forecasting engine with a real-time inventory platform, offering pharmacists and administrators an intelligent, data-driven tool to manage medicines, track expiry risks, process dispensing transactions, and maintain full audit compliance.

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
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
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

### 📊 Reporting & Analytics
- Sales reports (daily, all-time, per-pharmacist)
- Risk distribution charts by medicine category
- Admin dashboard with KPIs: total items, stock value, low-stock alerts, expiry risks

### 🔐 Security & Audit
- Role-based access control: `admin` and `pharmacist` roles
- Complete audit trail — every login, dispensing event, and settings change is logged
- System-level audit log viewer for administrators

### ⚙️ System Administration
- Staff management: create, edit, and delete user accounts
- Configurable system settings: hospital name, NHIS ID, currency, expiry threshold
- Database export/import (full JSON backup and restore)
- Database statistics dashboard

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Backend (Primary)** | Node.js, Express.js |
| **Backend (ML/API)** | Python, Flask, Waitress |
| **Database (Local)** | NeDB (embedded NoSQL) |
| **Database (Cloud)** | MongoDB Atlas |
| **Machine Learning** | scikit-learn (Random Forest), pandas, joblib |
| **Deployment** | Vercel (Serverless) |
| **Package Manager** | npm (Node), pip (Python) |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (Frontend)                │
│   login.html │ index.html │ inventory.html │ pos.html│
│   pharmacist.html │ reports.html │ settings.html    │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP / REST API
          ┌───────────┴────────────┐
          │                        │
  ┌───────▼────────┐    ┌──────────▼──────────┐
  │  Node.js/      │    │  Python Flask API   │
  │  Express       │    │  (app.py / api/)    │
  │  (server.js)   │    │  + ML Engine        │
  │  Port: 5051    │    │  Port: 5000         │
  └───────┬────────┘    └──────────┬──────────┘
          │                        │
  ┌───────▼────────┐    ┌──────────▼──────────┐
  │  NeDB (Local)  │    │   MongoDB Atlas     │
  │  *.db files    │    │   (Cloud / Vercel)  │
  └────────────────┘    └─────────────────────┘
```

---

## 📁 Project Structure

```
AI-Based/
│
├── 📂 api/                     # Vercel serverless function handlers (Python)
│   └── login.py                # Authentication serverless endpoint
│
├── 📂 public/                  # Frontend static files
│   ├── 📂 css/
│   │   └── style.css           # Global stylesheet
│   ├── 📂 js/                  # Frontend JavaScript modules
│   ├── index.html              # Admin Dashboard
│   ├── login.html              # Login Page
│   ├── inventory.html          # Inventory Management
│   ├── pos.html                # Point-of-Sale Terminal
│   ├── pharmacist.html         # Pharmacist Portal
│   ├── forecasting.html        # Demand Forecasting View
│   ├── reports.html            # Sales Reports
│   ├── audit.html              # Audit Log Viewer
│   ├── settings.html           # System Settings
│   └── users.html              # Staff Management
│
├── app.py                      # Python app entry point (local dev)
├── server.js                   # Node.js/Express backend server
├── ml_model.py                 # ML Intelligence Layer (Random Forest)
├── seed_db.py                  # Database seeding script
│
├── 📊 Data & Models
│   ├── project dataset.csv     # Source dataset (~500+ medicine records)
│   ├── model.pkl               # Pre-trained Random Forest model
│   ├── encoder.pkl             # Category Label Encoder
│   └── database.json           # JSON snapshot of inventory
│
├── 🗄️ Databases (NeDB)
│   ├── database.db             # Inventory
│   ├── users.db                # User accounts
│   ├── sales.db                # Sales transactions
│   ├── audit.db                # Audit log
│   └── settings.db             # System settings
│
├── package.json                # Node.js dependencies
├── requirements.txt            # Python dependencies
├── vercel.json                 # Vercel deployment config
├── .env                        # Environment variables (local only)
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

---

## 🚀 Getting Started

### Prerequisites

Ensure the following are installed on your machine:

- **Node.js** v18 or higher — [Download](https://nodejs.org/)
- **Python** 3.9 or higher — [Download](https://python.org/)
- **pip** (comes bundled with Python)
- **npm** (comes bundled with Node.js)

---

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/your-username/AI-Based.git
cd AI-Based
```

**2. Install Node.js dependencies**
```bash
npm install
```

**3. Install Python dependencies**
```bash
pip install -r requirements.txt
```

---

### Running the Application

#### Option A — Node.js Server (Recommended for local dev)

This runs the full Express backend serving all REST API endpoints and the frontend.

```bash
node server.js
```

The application will be available at: **http://localhost:5051**

---

#### Option B — Python/Flask Server (ML + Vercel-compatible)

This launches the Flask-based server which integrates with MongoDB Atlas and the ML model.

```bash
python app.py
```

The application will be available at: **http://localhost:5000**

---

#### Option C — Using npm scripts

```bash
# Python mode (default)
npm start

# Node.js mode (legacy)
npm run node-legacy
```

---

## 🔑 Default Credentials

> ⚠️ **Change these credentials immediately after first login in production.**

| Role | Username | Password | Access Level |
|---|---|---|---|
| Administrator | `admin` | `admin123` | Full system access |
| Pharmacist | `pharm` | `pharm123` | POS, inventory view, personal sales |

---

## 📡 API Reference

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

### Sales & POS
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/checkout` | Process a dispensing transaction |
| `GET` | `/api/sales/today` | Today's revenue and transaction count |
| `GET` | `/api/my/sales` | Pharmacist's personal sales history |

### Admin — Reporting
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/admin/sales` | All sales records |
| `GET` | `/api/system-audit` | Full system audit log |

### Admin — User Management
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/users` | List all staff accounts |
| `POST` | `/api/admin/users` | Create, edit, or delete a user (`action` field) |

### Admin — Settings & Database
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/settings` | Retrieve system settings |
| `POST` | `/api/settings` | Update system settings |
| `GET` | `/api/admin/db/stats` | Database statistics |
| `GET` | `/api/admin/db/export` | Export full database as JSON backup |
| `POST` | `/api/admin/db/import` | Restore database from JSON backup |

---

## 🧠 Machine Learning Model

The `PharmacyIntelligenceLayer` class in `ml_model.py` powers the AI engine.

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

### Expiry Risk Classification Logic
| Risk Level | Condition |
|---|---|
| **High Risk** | Days to expiry ≤ configured threshold (default: 30 days) |
| **Medium Risk** | Days to expiry ≤ threshold × 3 |
| **Low Risk** | All other cases |

### Model Files
- `model.pkl` — Serialized trained Random Forest model
- `encoder.pkl` — Serialized Label Encoder for drug categories

> The model is **pre-trained and saved to disk**. It loads automatically on server start without requiring re-training.

---

## 📄 Modules & Pages

| Page | Route | Role | Description |
|---|---|---|---|
| Login | `/login.html` | All | System authentication entry point |
| Dashboard | `/index.html` | Admin | KPIs, risk summary, recent alerts |
| Inventory | `/inventory.html` | Admin | Full inventory table with search |
| Forecasting | `/forecasting.html` | Admin | ML-driven demand & stockout forecast |
| POS Terminal | `/pos.html` | Pharmacist | Medicine dispensing and checkout |
| Pharmacist Portal | `/pharmacist.html` | Pharmacist | Personal dashboard and sales history |
| Reports | `/reports.html` | Admin | Sales reports and analytics |
| Audit Log | `/audit.html` | Admin | System-wide activity audit trail |
| Staff Management | `/users.html` | Admin | CRUD operations on user accounts |
| Settings | `/settings.html` | Admin | Hospital config, thresholds, DB tools |

---

## 🗄️ Database Design

The system uses **NeDB** (embedded, file-based NoSQL) for local deployment and **MongoDB Atlas** for cloud/Vercel deployment.

### Collections / Stores

**`database.db`** — Inventory
```json
{
  "Batch_ID": "B-1001",
  "Medicine_Name": "Paracetamol 500mg",
  "Category": "Analgesics",
  "Manufacturer": "Phyto-Riker",
  "Quantity_In_Stock": 250,
  "Unit_Cost_USD": 1.20,
  "Selling_Price_USD": 2.00,
  "Reorder_Level": 50,
  "Days_to_Expiry": 180,
  "Daily_Consumption_Rate": 8.5
}
```

**`users.db`** — Staff Accounts
```json
{
  "username": "admin",
  "password": "admin123",
  "role": "admin"
}
```

**`sales.db`** — Transactions
```json
{
  "timestamp": "2026-06-03T10:30:00.000Z",
  "pharmacist": "pharm",
  "customer_name": "John Mensah",
  "items": 3,
  "total_ghs": 45.00,
  "details": "2x Paracetamol, 1x Amoxicillin"
}
```

**`audit.db`** — Audit Log
```json
{
  "timestamp": "2026-06-03T10:30:00.000Z",
  "username": "pharm",
  "event": "Dispensed Medicine",
  "details": "Customer: John Mensah. Total: GH₵ 45.00."
}
```

**`settings.db`** — System Configuration
```json
{
  "hospital_name": "Ghana National Hospital",
  "nhis_id": "GHA-NHIS-9921",
  "expiry_threshold": 30,
  "currency": "GH₵"
}
```

---

## ☁️ Deployment

### Vercel (Cloud Deployment)

The project includes a `vercel.json` configuration for serverless deployment on Vercel with Python serverless functions.

**Steps:**
1. Install Vercel CLI: `npm i -g vercel`
2. Configure environment variables on Vercel dashboard (see below)
3. Deploy: `vercel --prod`

The Python API handlers in `/api/` are automatically picked up by Vercel as serverless functions.

---

## 🔧 Environment Variables

Create a `.env` file in the root directory for local development:

```env
# MongoDB Atlas Connection URI (for Flask/Vercel mode)
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/medai_gh?retryWrites=true&w=majority

# Server Port (optional, defaults to 5051 for Node.js)
PORT=5051
```

> ⚠️ **Never commit your `.env` file.** It is listed in `.gitignore`.

For Vercel deployment, set `MONGO_URI` directly in the **Vercel Project Dashboard → Settings → Environment Variables**.

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
