"""
Configuration — SLMG BI Portal
"""

import os
from datetime import timedelta


class Config:
    # ── Security ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'slmg-secret-2025-change-in-prod')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'slmg-jwt-2025-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get('JWT_EXPIRES_HOURS', 8)))

    # Headers-only — avoids all cookie/CSRF/HTTPS conflicts on Render
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    # ── Database ───────────────────────────────────────────────
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///slmg_portal.db')
    # Render/Heroku use postgres:// but SQLAlchemy needs postgresql://
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    # ── AI ────────────────────────────────────────────────────
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

    # ── App ───────────────────────────────────────────────────
    APP_NAME = 'SLMG Beverages BI Portal'
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
