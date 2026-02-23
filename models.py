"""
Database Models — SLMG BI Portal
"""

from app import db
from datetime import datetime
import json


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Viewer')  # Admin / Analyst / Viewer
    department = db.Column(db.String(50), nullable=False, default='Operations')  # Finance/Sales/HR/Operations
    bookmarks_raw = db.Column(db.Text, default='[]')  # JSON list of dashboard IDs
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    notes = db.relationship('Note', backref='author', lazy=True, cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='actor', lazy=True, cascade='all, delete-orphan')

    @property
    def bookmarks(self):
        try:
            return json.loads(self.bookmarks_raw or '[]')
        except Exception:
            return []

    @bookmarks.setter
    def bookmarks(self, value):
        self.bookmarks_raw = json.dumps(value)

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'department': self.department,
            'bookmarks': self.bookmarks,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        return data


class Dashboard(db.Model):
    __tablename__ = 'dashboards'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    embed_url = db.Column(db.Text, nullable=False)
    department = db.Column(db.String(50), nullable=False)  # Finance / Sales / HR / Operations
    category = db.Column(db.String(100), nullable=False)
    tags_raw = db.Column(db.Text, default='[]')          # JSON array
    kpis_raw = db.Column(db.Text, default='[]')          # JSON array of KPI objects
    commentary = db.Column(db.Text, default='')
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sort_order = db.Column(db.Integer, default=0)

    # Relationships
    notes = db.relationship('Note', backref='dashboard', lazy=True, cascade='all, delete-orphan')

    @property
    def tags(self):
        try:
            return json.loads(self.tags_raw or '[]')
        except Exception:
            return []

    @tags.setter
    def tags(self, value):
        self.tags_raw = json.dumps(value)

    @property
    def kpis(self):
        try:
            return json.loads(self.kpis_raw or '[]')
        except Exception:
            return []

    @kpis.setter
    def kpis(self, value):
        self.kpis_raw = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'embed_url': self.embed_url,
            'department': self.department,
            'category': self.category,
            'tags': self.tags,
            'kpis': self.kpis,
            'commentary': self.commentary,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sort_order': self.sort_order,
        }


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey('dashboards.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'dashboard_id': self.dashboard_id,
            'user_id': self.user_id,
            'author_name': self.author.name if self.author else 'Unknown',
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(200), nullable=False)   # e.g. "Created dashboard: Sales Q1"
    entity_type = db.Column(db.String(50))               # dashboard / user / system
    entity_id = db.Column(db.Integer, nullable=True)
    metadata_raw = db.Column(db.Text, default='{}')
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def metadata(self):
        try:
            return json.loads(self.metadata_raw or '{}')
        except Exception:
            return {}

    @metadata.setter
    def metadata(self, value):
        self.metadata_raw = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'actor_name': self.actor.name if self.actor else 'System',
            'actor_email': self.actor.email if self.actor else 'system',
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
