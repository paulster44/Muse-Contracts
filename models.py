# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

# Initialize SQLAlchemy extension instance
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Represents a registered user of the application."""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False) # Increased length for stronger hashes
    name = db.Column(db.String(100)) # Optional user name

    # Relationship to Contracts owned by the user
    # cascade="all, delete-orphan" ensures contracts are deleted if the user is deleted
    contracts = db.relationship('Contract', backref='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        """Hashes the password and stores it."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        """String representation for debugging."""
        return f'<User {self.id}: {self.email}>'

class SideMusician(db.Model):
    """Represents a side musician listed on a specific contract."""
    __tablename__ = 'side_musician'

    id = db.Column(db.Integer, primary_key=True)
    # Foreign key linking to the Contract table
    # ondelete='CASCADE' ensures side musicians are deleted if their contract is deleted
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id', ondelete='CASCADE'), nullable=False, index=True)

    # Musician details
    name = db.Column(db.String(150), nullable=False)
    card_no = db.Column(db.String(50)) # AFM Card Number
    tax_id = db.Column(db.String(50)) # Tax ID (SSN/EIN) - Use with caution (PII)
    instrument = db.Column(db.String(150)) # Can list multiple instruments, comma-separated?

    # Status flags relevant for calculations
    is_doubling = db.Column(db.Boolean, default=False, nullable=False) # Does the musician double at all?
    num_doubles = db.Column(db.Integer, default=0, nullable=False) # How many doublings? 0=none, 1=first, 2=first+add'l, etc.
    has_cartage = db.Column(db.Boolean, default=False, nullable=False) # Eligible for standard/SB cartage?
    is_principal = db.Column(db.Boolean, default=False, nullable=False) # Is this musician a principal player?
    is_concertmaster = db.Column(db.Boolean, default=False, nullable=False) # Is this musician the Concertmaster?

    def __repr__(self):
        """String representation for debugging."""
        return f'<SideMusician {self.id}: {self.name} for Contract {self.contract_id}>'

class Contract(db.Model):
    """Represents a single engagement contract."""
    __tablename__ = 'contract'

    id = db.Column(db.Integer, primary_key=True)
    # Foreign key linking to the User table (owner of the contract)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    # Contract status (e.g., draft, completed)
    status = db.Column(db.String(20), default='draft', nullable=False, index=True)

    # --- Scale Identification ---
    # Store keys used to look up rates in the SCALES dictionary from config.py
    applicable_local = db.Column(db.String(50), default='Local802', nullable=False) # e.g., 'Local802'
    applicable_scale = db.Column(db.String(100), default='ClassicalConcert_23_24', nullable=False) # e.g., 'ClassicalConcert_23_24'

    # --- Engagement Details ---
    engagement_date = db.Column(db.Date)
    leader_name = db.Column(db.String(150))
    leader_card_no = db.Column(db.String(50))
    leader_ssn_ein = db.Column(db.String(50)) # Leader's Tax ID (PII)
    leader_address = db.Column(db.String(250))
    leader_phone = db.Column(db.String(30))
    band_name = db.Column(db.String(150)) # Optional band/group name
    venue_name = db.Column(db.String(200))
    location_borough = db.Column(db.String(50)) # e.g., NYC, BKLYN, OOT
    engagement_type = db.Column(db.String(200)) # e.g., Concert, Wedding, Rehearsal Only
    num_musicians = db.Column(db.Integer, default=1) # Total count (Leader + Side Musicians), updated by calculation
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    has_rehearsal = db.Column(db.Boolean, default=False, nullable=False)
    pre_heat_hours = db.Column(db.Float) # Duration of pre-heat time, if any
    actual_hours_engagement = db.Column(db.Float) # Actual paid duration of performance
    actual_hours_rehearsal = db.Column(db.Float) # Actual paid duration of rehearsal
    is_recorded = db.Column(db.Boolean, default=False, nullable=False) # Performance recorded?
    leader_is_incorporated = db.Column(db.Boolean, default=False, nullable=False) # Leader signing as corporation?

    # --- Leader Specific Statuses ---
    # Storing leader's details directly on Contract simplifies things vs. separate Leader model
    leader_instrument = db.Column(db.String(150))
    leader_is_playing = db.Column(db.Boolean, default=True, nullable=False) # Is the leader performing?
    leader_is_principal = db.Column(db.Boolean, default=False, nullable=False) # Is the leader also a principal?
    leader_is_concertmaster = db.Column(db.Boolean, default=False, nullable=False) # Is the leader the Concertmaster?
    leader_has_cartage = db.Column(db.Boolean, default=False, nullable=False) # Does leader get standard/SB cartage?
    leader_is_doubling = db.Column(db.Boolean, default=False, nullable=False) # Does the leader double?
    leader_num_doubles = db.Column(db.Integer, default=0, nullable=False) # How many doubles for the leader?

    # --- Calculation Results ---
    # Store the calculated monetary values rounded to cents (or use Decimal type if precision is critical)
    total_gross_comp = db.Column(db.Float) # Total scale wages (incl. OT, premiums) before benefits/dues
    total_work_dues = db.Column(db.Float) # Calculated work dues amount
    total_pension = db.Column(db.Float) # Calculated pension contribution
    total_health = db.Column(db.Float) # Calculated health benefit contribution

    # --- Timestamps ---
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_saved_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # --- Relationships ---
    # Defines the one-to-many relationship with SideMusician
    side_musicians = db.relationship('SideMusician', backref='contract', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        """String representation for debugging."""
        return f'<Contract {self.id} for User {self.user_id} on {self.engagement_date}>'
