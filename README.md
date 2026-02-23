# 🔴 SLMG Beverages — Enterprise BI Portal

> Production-ready Power BI Enterprise Dashboard Portal  
> Built with Flask · SQLAlchemy · JWT Authentication · Vanilla JS · Tailwind CSS

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- Python 3.10+
- Git

### 1️⃣ Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/slmg-bi-portal.git
cd slmg-bi-portal

python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2️⃣ Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and update:
- SECRET_KEY
- JWT_SECRET_KEY
- DATABASE_URL (if using PostgreSQL)

### 3️⃣ Run Application

```bash
python app.py
```

Open in browser:
```
http://localhost:5000
```

---

## 🔐 Default Login Credentials

| Email | Password | Role | Department |
|--------|----------|--------|------------|
| admin@slmg.com | Admin@1234 | Admin | Operations |
| finance@slmg.com | Finance@1234 | Analyst | Finance |
| sales@slmg.com | Sales@1234 | Analyst | Sales |
| hr@slmg.com | HR@1234 | Viewer | HR |

⚠️ Change all passwords before production deployment.

---

## 🏗️ Project Structure

```
slmg-bi-portal/
│
├── app.py
├── config.py
├── models.py
├── requirements.txt
├── Procfile
├── .env.example
│
├── routes/
│   ├── auth.py
│   ├── dashboards.py
│   ├── users.py
│   └── analytics.py
│
├── services/
│   ├── kpi_service.py
│   ├── swot_service.py
│   └── ai_service.py
│
├── middleware/
│   └── auth_middleware.py
│
└── templates/
    └── index.html
```

---

## 🔒 Security Model

Department-Based Access Control (Server-Side Enforced)

- Admin → Access to all dashboards
- Finance → Finance dashboards only
- Sales → Sales dashboards only
- HR → HR dashboards only
- Operations → Operations dashboards only

Access filtering is enforced in:
```
middleware/auth_middleware.py
```

Security is enforced on backend — not only on frontend.

---

## 📊 API Overview

### Authentication
- POST `/api/auth/login`
- POST `/api/auth/logout`
- GET `/api/auth/me`
- PUT `/api/auth/profile`

### Dashboards
- GET `/api/dashboards/`
- GET `/api/dashboards/:id`
- POST `/api/dashboards/`
- PUT `/api/dashboards/:id`
- DELETE `/api/dashboards/:id`
- POST `/api/dashboards/:id/bookmark`
- GET/POST `/api/dashboards/:id/notes`

### Analytics
- GET `/api/analytics/kpis/:id`
- GET `/api/analytics/swot/:id`
- POST `/api/analytics/ai-summary/:id`
- POST `/api/analytics/compare`
- GET `/api/analytics/portfolio`

### Users (Admin Only)
- GET `/api/users/`
- POST `/api/users/`
- PUT `/api/users/:id`
- DELETE `/api/users/:id`
- GET `/api/users/activity-log`

---

## ☁️ Deploy on Render

### Build Command
```
pip install -r requirements.txt
```

### Start Command
```
gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
```

### Environment Variables
```
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret
DATABASE_URL=your_database_url
JWT_COOKIE_SECURE=true
ANTHROPIC_API_KEY=optional
```

---

## 🤖 AI Insights

Two operating modes:

1. With ANTHROPIC_API_KEY  
   → Uses Claude API for executive summaries

2. Without API Key  
   → Built-in rule-based analytics engine

Both use real KPI values and trends.

---

## 🎨 Key Features

- Role + Department Based Access Control
- Power BI Embed Integration
- KPI Health Engine (Green / Yellow / Red)
- SWOT Generator
- AI Executive Summary
- Bookmark System
- Notes per Dashboard
- Activity Log
- Auto Refresh
- Dark / Light Mode
- Admin User Management
- JWT Authentication
- Fully Responsive UI

---

## 🔧 Development

Run in debug mode:

```bash
DEBUG=true python app.py
```

Reset database:

```bash
rm slmg_portal.db
python app.py
```

---

© 2025 SLMG Beverages Pvt. Ltd.
