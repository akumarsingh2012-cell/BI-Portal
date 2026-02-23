# 🔴 SLMG Beverages — Enterprise BI Portal

> **Production-ready Power BI Enterprise Dashboard Portal**  
> Built with Flask · SQLAlchemy · JWT Authentication · Vanilla JS · Tailwind CSS

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.10+
- Git

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/slmg-bi-portal.git
cd slmg-bi-portal

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — at minimum, change SECRET_KEY and JWT_SECRET_KEY
```

### 3. Run

```bash
python app.py
```

Open: **http://localhost:5000**

---

## 🔐 Default Login Credentials

| Email | Password | Role | Department |
|-------|----------|------|------------|
| admin@slmg.com | Admin@1234 | **Admin** | Operations |
| finance@slmg.com | Finance@1234 | Analyst | Finance |
| sales@slmg.com | Sales@1234 | Analyst | Sales |
| hr@slmg.com | HR@1234 | Viewer | HR |

> ⚠️ **Change all passwords immediately in production!**

---

## 🏗️ Architecture

```
slmg-bi-portal/
├── app.py                  # Flask app factory + DB seeding
├── config.py               # Configuration (env vars)
├── models.py               # SQLAlchemy models
├── requirements.txt
├── Procfile                # Gunicorn (Render/Heroku)
├── .env.example
│
├── routes/
│   ├── auth.py             # Login, logout, profile
│   ├── dashboards.py       # CRUD, bookmarks, notes
│   ├── users.py            # User management (Admin)
│   └── analytics.py        # KPI, SWOT, AI endpoints
│
├── services/
│   ├── kpi_service.py      # KPI health + trend engine
│   ├── swot_service.py     # Data-driven SWOT generator
│   └── ai_service.py       # Anthropic AI + rule-based fallback
│
├── middleware/
│   └── auth_middleware.py  # JWT + department enforcement
│
└── templates/
    └── index.html          # Full SPA frontend
```

---

## 🔒 Security Model

### Department-Based Access Control (Enforced Server-Side)

```
Admin     → Sees ALL dashboards across all departments
Finance   → ONLY sees Finance dashboards
Sales     → ONLY sees Sales dashboards
HR        → ONLY sees HR dashboards
Operations→ ONLY sees Operations dashboards
```

**Critical**: Filtering is enforced in `middleware/auth_middleware.py → department_filter()`.  
It is **never** applied solely on the frontend.

---

## 📊 API Endpoints

### Auth
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/auth/login` | Login → returns JWT |
| POST | `/api/auth/logout` | Logout (clear cookie) |
| GET | `/api/auth/me` | Current user profile |
| PUT | `/api/auth/profile` | Update name/password |

### Dashboards
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/dashboards/` | List (filtered by dept) |
| GET | `/api/dashboards/:id` | Get one with KPIs |
| POST | `/api/dashboards/` | Create (Analyst+Admin) |
| PUT | `/api/dashboards/:id` | Update |
| DELETE | `/api/dashboards/:id` | Delete (Admin) |
| POST | `/api/dashboards/:id/bookmark` | Toggle bookmark |
| GET/POST | `/api/dashboards/:id/notes` | Notes |

### Analytics
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/analytics/kpis/:id` | KPI health + trends |
| GET | `/api/analytics/swot/:id` | SWOT analysis |
| POST | `/api/analytics/ai-summary/:id` | AI executive brief |
| POST | `/api/analytics/compare` | Side-by-side compare |
| GET | `/api/analytics/portfolio` | Portfolio health |

### Users (Admin Only)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/users/` | List all users |
| POST | `/api/users/` | Create user |
| PUT | `/api/users/:id` | Update user |
| DELETE | `/api/users/:id` | Delete user |
| GET | `/api/users/activity-log` | Activity log |

---

## ☁️ Deploy on Render (Free)

### Step 1: GitHub
```bash
git init
git add .
git commit -m "Initial commit: SLMG BI Portal"
git remote add origin https://github.com/YOUR_USERNAME/slmg-bi-portal.git
git push -u origin main
```

### Step 2: Render Setup
1. Go to **https://render.com** → New → **Web Service**
2. Connect your GitHub repo
3. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn "app:create_app()" --bind 0.0.0.0:$PORT`
   - **Runtime**: Python 3.11

### Step 3: Environment Variables (Render Dashboard)
```
SECRET_KEY          = [generate a strong random key]
JWT_SECRET_KEY      = [generate a strong random key]
JWT_COOKIE_SECURE   = true
DATABASE_URL        = [your PostgreSQL URL from Render DB or Neon.tech]
ANTHROPIC_API_KEY   = [optional — enables AI summaries]
```

### Step 4: Database
- **Free Option**: Render provides a free PostgreSQL instance
- **Alternative**: Use [Neon.tech](https://neon.tech) (free serverless PostgreSQL)
- Update `DATABASE_URL` with the connection string

### Step 5: Deploy
Click **Deploy** — Render builds and runs automatically. ✅

---

## ☁️ Deploy on Railway

```bash
railway init
railway add
railway up
```
Set environment variables in Railway dashboard.

---

## ☁️ Deploy on Heroku

```bash
heroku create slmg-bi-portal
heroku addons:create heroku-postgresql:essential-0
heroku config:set SECRET_KEY=yourkey JWT_SECRET_KEY=yourkey
git push heroku main
```

---

## 🤖 AI Insights

The portal has two modes:

1. **With `ANTHROPIC_API_KEY`**: Uses Claude API to generate real executive summaries
2. **Without API Key**: Built-in rule-based engine generates analytics from KPI data

Both modes use actual KPI values, targets, and trends — never placeholder text.

---

## 🎨 Features

- ✅ Role + Department-Based Access Control (server-side enforced)
- ✅ Power BI iframe embed with lazy loading (IntersectionObserver)
- ✅ Real KPI Health Engine (GREEN/YELLOW/RED)
- ✅ Real SWOT Generator (data-driven, not placeholder)
- ✅ AI Executive Briefing (Claude API or rule-based fallback)
- ✅ Voice Summary (Web Speech API)
- ✅ Side-by-Side Comparison Mode
- ✅ Bookmark System (persisted in DB)
- ✅ Notes History per Dashboard
- ✅ Activity Log
- ✅ Auto-Refresh Toggle (30s interval)
- ✅ Dark/Light Mode
- ✅ Grid/List View Toggle
- ✅ Admin: User Management (Create/Edit/Delete)
- ✅ JWT Authentication (HTTP-only cookie)
- ✅ Fully responsive design
- ✅ SLMG Beverages branding + Coca-Cola color theme

---

## 📝 Adding Real Power BI Dashboards

1. In Power BI Service → Open your report
2. Click **File** → **Embed report** → **Website or portal**
3. Copy the embed URL (starts with `https://app.powerbi.com/reportEmbed...`)
4. Log in as Admin → **Add Dashboard** → Paste the URL

---

## 🔧 Development

```bash
# Run in debug mode
DEBUG=true python app.py

# Reset database
rm slmg_portal.db
python app.py  # Will re-seed automatically
```

---

*© 2025 SLMG Beverages Pvt. Ltd. — United to Grow Ahead*
