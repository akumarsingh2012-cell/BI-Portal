"""
Configuration for SLMG BI Portal
"""

import os
from datetime import timedelta


class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'slmg-secret-key-change-in-production-2025')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'slmg-jwt-secret-change-in-production-2025')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get('JWT_EXPIRES_HOURS', 8)))
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_COOKIE_SECURE = os.environ.get('JWT_COOKIE_SECURE', 'false').lower() == 'true'
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_CSRF_PROTECT = False  # Disable for simplicity; enable in production with proper CSRF

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///slmg_portal.db'
    )
    # Fix for Heroku/Render PostgreSQL URL format
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    # AI (Anthropic)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

    # App
    APP_NAME = 'SLMG Beverages BI Portal'
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
