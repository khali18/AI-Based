# AI-Based Medicine Stock and Expiry Prediction System for Hospitals
## Technical Project Defense & Resource Guide

This document serves as the primary technical resource for defending this **AI-enhanced Hospital System**. It outlines the architecture, intelligence logic, and robustness features that ensure clinical safety and inventory foresight.

---

## 1. Project Abstract & Vision
**Topic Alignment**: This system is specifically designed to solve the two biggest challenges in hospital pharmacy management: **Stockouts** and **Medical Waste (Expiry)**.
- **Stock Prediction**: Accomplished via the Random Forest Demand Model.
- **Expiry Prediction**: Accomplished via the Inventory Risk Classifier.
- **Hospital Context**: Accomplished via the Role-Based Access Control and Session Auditing.

---

## 2. Technical Architecture (The Tech Stack)
A robust "defense" starts with explaining why you chose your tools:

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend** | Python / Flask | Highly scalable with large libraries for AI/ML. |
| **Server** | Waitress (WSGI) | Production-grade multi-threaded server (prevents crashing during mid-demo). |
| **Database** | TinyDB (NoSQL) | Document-based storage; ideal for clinical records with flexible metadata. |
| **Frontend** | Vanilla JS / CSS3 | Optimized for speed (no heavy frameworks) with a premium Glassmorphism UI. |
| **Intelligence** | Scikit-Learn | Industry-standard library for the Random Forest Regressor. |

---

## 3. The "Intelligence" Layer (AI & ML)
Examiners will focus here. Be prepared to explain:

### A. Demand Forecasting (Random Forest Regressor)
**Logic**: The system uses a **Random Forest Regressor** trained on historical sales data, unit costs, and categories. 
- **Input Features**: `Unit_Cost_USD`, `Category`, `Sales_Last_30_Days`.
- **Output**: `ML_Predicted_Consumption` (Daily rate).
- **Why Random Forest?**: It is an ensemble method that reduces "overfitting" and provides more stable predictions than a single decision tree.

### B. Automated Expiry Risk Classifier
Your system doesn't just look at dates; it looks at **Probability of Utilization**:
- **Formula**: `(Current_Stock / Predicted_Daily_Sales) > Days_to_Expiry`
- **Impact**: If you have 100 tablets and sell 1 per day, but they expire in 50 days, the AI marks this as **High Risk** because you will lose 50 tablets. Traditional systems would miss this.

### C. Business Intelligence (BI) Metrics
The system performs real-time financial aggregation:
- **Timeframe Filtering**: SQL-like grouping of sales into **Daily**, **Monthly**, and **Annual** chunks.
- **Revenue KPIs**: Direct synchronization between Pharmacist sales and Admin dashboard (Live Revenue).

---

## 4. System Robustness & Performance

### 🛡️ Self-Healing Database
Explain how the system handles crashes:
- **Detection**: On boot, `app.py` performs a read check.
- **Action**: If a `JSONDecodeError` (corruption) is found, the system **automatically purges** the corrupted file and **re-seeds** from the source CSV in milliseconds. 
- **Benefit**: 100% uptime regardless of power outages or rapid restarts.

### 🧵 Multi-threaded Processing & Thread Safety
- The server is configured with `threads=4` via Waitress. 
- **Thread-Safe Logic**: I implemented a `db_lock` (threading mutex) in Python to ensure that if two pharmacists sell at the same microsecond, the database file is never corrupted during the write process.

---

## 5. User Personalization & Clinical Accountability
- **Profile Management**: Support for secure profile picture uploads with smart fallback avatars (using `ui-avatars.com`) if no image is uploaded.
- **Audit Traceability**: Every transaction is logged with the user's name and profile image, ensuring total visual accountability during system audits.

---

## 6. Defense Q&A (Be Ready!)

**Q1: Why use TinyDB instead of MySQL?**
*   **Answer**: For this clinical scale, TinyDB provides a lightweight, NoSQL document store that allows for complex metadata in audit logs without rigid schema migrations. It makes the system faster to deploy in resource-constrained environments.

**Q2: How do you handle non-linear demand in your AI?**
*   **Answer**: By using a **Random Forest Regressor**. It captures non-linear relationships between cost, category, and sales history better than simple Linear Regression.

**Q3: Is the system secure?**
*   **Answer**: Yes. It implements **Role-Based Access Control (RBAC)**. Pharmacists cannot access financial reports or delete users; only the System Admin has those privileges.

---

## 7. How to Demo (Pro Tips)
1.  **Start the Server**: Show the terminal training the model at boot (`python app.py`).
2.  **Point of Sale**: Perform a sale as a Pharmacist (`pharm / pharm123`).
3.  **Revenue Sync**: Immediately switch to Admin (`admin / admin123`) and show the **Today's Revenue** card updated.
4.  **Forecasting**: Point to the "Predictions" column in Inventory to show the AI's "Days to Exhaust" foresight.
5.  **Multi-Timeframe Reports**: Open the Reports tab and switch between **Today**, **Month**, and **Year** to show the dynamic data aggregation.

---
**MedAI GH: Precision Medicine Through Intelligent Management.**
