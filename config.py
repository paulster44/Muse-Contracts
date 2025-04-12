# config.py

import os

# --- Secret Key (Loaded from .env file by app.py using load_dotenv) ---
# Ensure you have a SECRET_KEY set in your .env file for production!
# Example .env line: SECRET_KEY='a_very_long_and_random_string_here'
SECRET_KEY = os.environ.get('SECRET_KEY') # app.py provides fallback if None/empty

# --- Database Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Ensure the instance folder exists (app.py typically handles this, but good practice)
INSTANCE_FOLDER_PATH = os.path.join(BASE_DIR, 'instance')
# Define the default database path within the instance folder
DEFAULT_DB_PATH = os.path.join(INSTANCE_FOLDER_PATH, 'app.db')
# Use DATABASE_URL from environment if available, otherwise default to SQLite in instance folder
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{DEFAULT_DB_PATH}')
# Disable modification tracking to save resources, as Flask-SQLAlchemy handles it
SQLALCHEMY_TRACK_MODIFICATIONS = False

# --- Application Settings ---
# Enable debug mode if FLASK_DEBUG environment variable is set to '1'
DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'

# --- AFM Scale Rates ---
# Structure: SCALES['LocalKey']['ScaleKey']['RATE_NAME']
# Use lowercase for lists that will be matched against user input (instruments)
SCALES = {
    'Local802': {
        'ClassicalConcert_23_24': {
            # --- METADATA ---
            'NAME': 'Local 802 - Classical Concert (15+ musicians, 23-24)',
            'EFFECTIVE_START': '2023-09-12',
            'EFFECTIVE_END': '2024-09-11',

            # --- PERFORMANCE ---
            'PERFORMANCE_MIN_HOURS': 2.5,
            'PERFORMANCE_BASE': 333.91,          # Pay for first 2.5 hours or less
            'PERF_PRINCIPAL_BASE': 400.69,       # Base pay including principal premium (2.5 hrs or less)
            'PERF_OT_UNIT_MINS': 15,
            'PERF_OT_RATE': 50.09,               # Standard OT rate per unit
            'PERF_OT_PRINCIPAL_RATE': 60.10,     # Standard OT rate per unit w/ principal premium
            'PERF_OT_RATE_MIDNIGHT': 66.78,        # OT rate per unit past midnight
            'PERF_OT_PRINCIPAL_RATE_MIDNIGHT': 80.14, # OT rate per unit past midnight w/ principal premium
            # Special Case: Performance starting at midnight or later (Needs specific handling in calc logic)
            'PERF_RATE_ALL_MIDNIGHT': 500.87,      # Flat rate if starts >= midnight
            'PERF_PRINCIPAL_RATE_ALL_MIDNIGHT': 601.04, # Flat rate if starts >= midnight w/ principal premium

            # --- REHEARSAL (Day - ends <= 7pm) ---
            'REHEARSAL_DAY_MIN_CALL_HOURS': 2.5,
            'REHEARSAL_DAY_MIN_CALL_PAY': 167.78,     # Pay for first 2.5 hours
            'REHEARSAL_DAY_PRINCIPAL_MIN_CALL_PAY': 201.34, # Min call pay w/ principal premium
            'REHEARSAL_DAY_MAX_CALL_HOURS': 4.0,
            'REHEARSAL_DAY_HOURLY_RATE': 67.11,       # Straight time rate per hour (e.g., between 2.5 and 4 hrs?)
            'REHEARSAL_DAY_PRINCIPAL_HOURLY_RATE': 80.54, # Straight time hourly w/ principal premium
            'REH_DAY_OT_UNIT_MINS': 30,
            'REH_DAY_OT_RATE': 50.33,               # OT rate per unit past last call
            'REH_DAY_OT_PRINCIPAL_RATE': 60.40,     # OT rate per unit past last call w/ principal premium

            # --- REHEARSAL (Night - ends > 7pm) ---
            # According to PDF notes, night rehearsals use performance scale/rates
            'REHEARSAL_NIGHT_IS_PERFORMANCE_RATE': True, # Flag to indicate using perf rates
            # Redundant values if flag is True, but kept for potential direct access/clarity
            'REH_NIGHT_MIN_HOURS': 2.5, # Based on performance minimum
            'REH_NIGHT_BASE': 333.91,   # Based on performance base
            'REH_NIGHT_PRINCIPAL_BASE': 400.69, # Based on performance principal base
            'REH_NIGHT_OT_UNIT_MINS': 15, # Based on performance OT unit
            'REH_NIGHT_OT_RATE': 50.09,  # Based on performance OT rate
            'REH_NIGHT_OT_PRINCIPAL_RATE': 60.10, # Based on performance OT principal rate

            # --- PREMIUMS (Percentages applied to relevant base+OT scale wages) ---
            'CONCERTMASTER_PREMIUM_PERCENT': 1.00, # 100% (Applied instead of Principal)
            'PRINCIPAL_PREMIUM_PERCENT': 0.20,   # 20%
            'PRINCIPAL_INSTRUMENTS': [ # Use lowercase for matching
                'second violin', 'viola', 'cello', 'bass', 'flute', 'oboe',
                'clarinet', 'bassoon', 'french horn', 'trumpet', 'trombone',
                'tuba', 'timpani', 'percussion', 'harp', 'keyboard'
            ],
            'LEADER_PREMIUM_PERCENT': 1.00,      # 100% (Conditional: Playing Leader, No CM - Handle in code)

            # --- DOUBLING (Percentages applied to relevant base+OT scale wages) ---
            'DOUBLING_FIRST_PREMIUM_PERCENT': 0.20,  # 20%
            'DOUBLING_ADDITIONAL_PREMIUM_PERCENT': 0.10, # 10%
            # Families where switching within is NOT doubling (Simplified - Needs refinement based on precise rules)
            'DOUBLING_EXCLUDED_FAMILIES': [
                 # Store main family names, code can check variations if needed
                'clarinet', 'trumpet', 'trombone', 'tuba',
                # Group percussion/etc. - This may need more granular logic based on actual rules
                'percussion', 'timpani', 'mallets', 'drum set', 'ethnic percussion', 'latin percussion'
            ],

            # --- BENEFITS ---
            'PENSION_RATE': 0.1799,             # 17.99% of gross scale (excl. taxable cartage)
            'HEALTH_PER_PERFORMANCE': 84.00,
            'HEALTH_PER_REHEARSAL': 31.50,
            'WORK_DUES_RATE': 0.035,              # 3.5% of gross scale (excl. taxable cartage)

            # --- CARTAGE (Fixed Rates - Taxable, added AFTER Pension/Dues calc) ---
            'CARTAGE_RATE_STD': 29.94,
            'CARTAGE_INSTRUMENTS_STD': [ # Use lowercase
                'cello', 'bass clarinet', 'contrabass clarinet',
                'contrabassoon', 'tuba'
            ],
            'CARTAGE_RATE_SB': 49.04,
            'CARTAGE_INSTRUMENTS_SB': ['string bass'], # Use lowercase
            # List instruments requiring 'Actual Cost' cartage (non-taxable, manual handling needed)
            'CARTAGE_ACTUAL_COST_INSTRUMENTS': [ # Use lowercase
                'timpani', 'harpsichord', 'harp', 'xylophone', 'vibraphone',
                'marimba', 'bass drum', 'celesta'
            ],

             # --- SOUND CHECK (Requires specific conditions) ---
            'SOUND_CHECK_RATE': 100.67,          # Base rate for 1 hour or less
            'SOUND_CHECK_PRINCIPAL_RATE': 120.80, # Rate including principal premium
            'SOUND_CHECK_MAX_HOURS': 1.0,        # Duration covered by the rate

        },
        # --- Add 'ChamberMusic_23_24' scale definition here later ---
        # Example placeholder:
        # 'ChamberMusic_23_24': {
        #     'NAME': 'Local 802 - Chamber Music (<=14 musicians, 23-24)',
        #     # ... populate with rates from PDF page 3 ...
        # },
        # --- Add 'ReligiousService_23_24' scale definition here later ---
        # Example placeholder:
        # 'ReligiousService_23_24': {
        #     'NAME': 'Local 802 - Religious Service (23-24)',
        #     # ... populate with rates from PDF page 3/4 ...
        # },
    },
    # --- Add other Locals here later ---
    # Example placeholder:
    # 'OtherLocal': {
    #     'StandardScale_YY_ZZ': {
    #          'NAME': 'Other Local - Standard Scale',
    #          # ... populate with rates ...
    #     }
    # }
}
