# config.py

import os

# --- Secret Key (Loaded from .env file by app.py using load_dotenv) ---
SECRET_KEY = os.environ.get('SECRET_KEY') # app.py provides fallback if None

# --- Database Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_FOLDER_PATH = os.path.join(BASE_DIR, 'instance')
DEFAULT_DB_PATH = os.path.join(INSTANCE_FOLDER_PATH, 'app.db')
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', f'sqlite:///{DEFAULT_DB_PATH}')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# --- Application Settings ---
DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1' # Set via FLASK_DEBUG=1

# --- AFM Scale Rates ---
# Structure: SCALES['LocalXXX']['EngagementType_YY_ZZ']['RATE_NAME']
SCALES = {
    'Local802': {
        'ClassicalConcert_23_24': {
            # Performance
            'PERFORMANCE_BASE': 333.91,       # 2.5 hrs or less
            'PERFORMANCE_PRINCIPAL_PREMIUM': 1.20, # Multiplier
            'PERF_OT_UNIT_MINS': 15,
            'PERF_OT_RATE': 50.09,
            'PERF_OT_PRINCIPAL_RATE': 60.10,
            # Rehearsal
            'REHEARSAL_MIN_CALL': 167.78,      # 2.5 hr min call
            'REHEARSAL_HOURLY': 67.11,
            'REHEARSAL_PRINCIPAL_PREMIUM': 1.20, # Multiplier
            'REH_OT_UNIT_MINS': 30,            # Day Rehearsal OT
            'REH_OT_RATE': 50.33,
            'REH_OT_PRINCIPAL_RATE': 60.40,
            # Premiums / Addons
            'DOUBLING_FIRST_PREMIUM': 0.20,    # Percentage
            'CARTAGE_CELLO_BASS_ETC': 29.94,
            'CARTAGE_STRING_BASS': 49.04,
            # Contributions
            'PENSION_RATE': 0.1799,            # 17.99%
            'HEALTH_PER_PERFORMANCE': 84.00,
            'HEALTH_PER_REHEARSAL': 31.50,
            'WORK_DUES_RATE': 0.035,           # 3.5%
            # Lists used by helpers
            'PRINCIPAL_INSTRUMENTS': [
                "second violin", "viola", "cello", "bass", "flute", "oboe",
                "clarinet", "bassoon", "french horn", "trumpet", "trombone",
                "tuba", "timpani", "percussion", "harp", "keyboard"
            ],
            'CARTAGE_INSTRUMENTS_STD': ["cello", "contrabass clarinet", "contrabassoon", "tuba"],
            'CARTAGE_INSTRUMENTS_SB': ["string bass", "bass"]
        },
        # Add other Local 802 scales here...
    },
    # Add other Locals here...
}

# You could define the lists globally here if they are truly universal,
# but keeping them within the scale dictionary might be better for future flexibility.
# PRINCIPAL_INSTRUMENTS = [...]
# CARTAGE_INSTRUMENTS_STD = [...]
# CARTAGE_INSTRUMENTS_SB = [...]
