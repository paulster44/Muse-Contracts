# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100))
    contracts = db.relationship('Contract', backref='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def __repr__(self): return f'<User {self.id}: {self.email}>'

class SideMusician(db.Model):
    __tablename__ = 'side_musician'
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    card_no = db.Column(db.String(50))
    tax_id = db.Column(db.String(50)) # Renamed from ssn
    instrument = db.Column(db.String(100))
    is_doubling = db.Column(db.Boolean, default=False)
    has_cartage = db.Column(db.Boolean, default=False)
    def __repr__(self): return f'<SideMusician {self.id}: {self.name} for Contract {self.contract_id}>'

class Contract(db.Model):
    __tablename__ = 'contract'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(20), default='draft', nullable=False, index=True)
    # --- NEW Fields for Scale Identification ---
    applicable_local = db.Column(db.String(50), default='Local802') # Example default
    applicable_scale = db.Column(db.String(100), default='ClassicalConcert_23_24') # Example default
    # --- Existing Fields ---
    engagement_date = db.Column(db.Date); leader_name = db.Column(db.String(150))
    leader_card_no = db.Column(db.String(50)); leader_ssn_ein = db.Column(db.String(50))
    leader_address = db.Column(db.String(250)); leader_phone = db.Column(db.String(30))
    band_name = db.Column(db.String(150)); venue_name = db.Column(db.String(200))
    location_borough = db.Column(db.String(50)); engagement_type = db.Column(db.String(200))
    num_musicians = db.Column(db.Integer, default=1) # Updated by calculation now
    start_time = db.Column(db.Time); end_time = db.Column(db.Time)
    has_rehearsal = db.Column(db.Boolean, default=False); pre_heat_hours = db.Column(db.Float)
    actual_hours_engagement = db.Column(db.Float); actual_hours_rehearsal = db.Column(db.Float)
    is_recorded = db.Column(db.Boolean, default=False); leader_is_incorporated = db.Column(db.Boolean, default=False)
    # Calculation Results
    total_gross_comp = db.Column(db.Float); total_work_dues = db.Column(db.Float)
    total_pension = db.Column(db.Float); total_health = db.Column(db.Float)
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_saved_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Relationships
    side_musicians = db.relationship('SideMusician', backref='contract', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self): return f'<Contract {self.id} for User {self.user_id} on {self.engagement_date}>'
