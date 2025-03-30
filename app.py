# app.py
import os
import datetime
import logging
import math
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
# --- WeasyPrint imports are COMMENTED OUT for local running ---
# from flask_weasyprint import HTML, render_pdf
# from flask import make_response
# --- END COMMENT OUT ---
from models import db, User, Contract, SideMusician # Ensure models.py is correct
from sqlalchemy.exc import IntegrityError

# Load environment variables from .env file (primarily for SECRET_KEY)
load_dotenv()

# Create Flask app instance
app = Flask(__name__, instance_relative_config=True)

# --- Load Configuration ---
try:
    # Load defaults from config.py in the application root
    app.config.from_object('config')
except ImportError:
    app.logger.error("FATAL: config.py not found. Cannot start.")
    exit() # Exit if main config is missing
except Exception as e:
     app.logger.error(f"FATAL: Error loading config.py: {e}")
     exit()

# Ensure the instance folder exists (needed for SQLite)
try:
    if not os.path.exists(app.instance_path): os.makedirs(app.instance_path)
except OSError: app.logger.error("Could not create instance folder! Check permissions.")

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO
app.logger.setLevel(log_level) # Use DEBUG to see calculation logs
if app.config.get('SECRET_KEY', '').startswith('fallback') or not app.config.get('SECRET_KEY'):
    app.logger.critical("CRITICAL SECURITY WARNING: SECRET_KEY not set or using fallback! Set in .env file.")

# --- Initialize Flask Extensions ---
try:
    db.init_app(app); bcrypt = Bcrypt(app); login_manager = LoginManager(app)
except Exception as e: app.logger.critical(f"Failed init extensions: {e}", exc_info=True)
login_manager.login_view = 'login'; login_manager.login_message_category = 'info'

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    if user_id is None or not user_id.isdigit(): return None
    try: return User.query.get(int(user_id))
    except Exception as e: app.logger.error(f"Error loading user {user_id}: {e}", exc_info=True); return None

# --- Context Processor ---
@app.context_processor
def inject_now(): return {'now': datetime.datetime.utcnow()}

# --- Helper Functions ---
def parse_time_safe(time_str):
    if not time_str: return None
    try: return datetime.datetime.strptime(time_str, '%H:%M').time()
    except ValueError: app.logger.warning(f"Failed parse time: {time_str}"); return None
def parse_date_safe(date_str):
    if not date_str: return None
    try: return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: app.logger.warning(f"Failed parse date: {date_str}"); return None
def parse_float_safe(float_str):
    if float_str is None or str(float_str).strip() == '': return None
    try: return float(float_str)
    except (ValueError, TypeError): app.logger.warning(f"Failed parse float: {float_str}"); return None

# --- Helpers using Config ---
def is_principal(instrument_string, scale_config): # Takes scale_config dict
    """Checks if any principal instrument is mentioned (case-insensitive)."""
    if not instrument_string or not scale_config: return False
    principal_list = scale_config.get('PRINCIPAL_INSTRUMENTS', [])
    if not principal_list: app.logger.warning("PRINCIPAL_INSTRUMENTS list empty in scale config."); return False
    return any(p.lower() in instrument_string.lower() for p in principal_list)

def get_cartage_fee(instrument_string, has_cartage_flag, scale_config): # Takes scale_config dict
    """Determines cartage fee based on instrument and flag using scale_config."""
    if not has_cartage_flag or not instrument_string or not scale_config: return 0.0
    inst_lower = instrument_string.lower()
    # Get lists and rates from the specific scale config passed in
    sb_list = scale_config.get('CARTAGE_INSTRUMENTS_SB', [])
    std_list = scale_config.get('CARTAGE_INSTRUMENTS_STD', [])
    sb_rate = scale_config.get('SCALE_CARTAGE_STRING_BASS', 0.0)
    std_rate = scale_config.get('SCALE_CARTAGE_CELLO_BASS_ETC', 0.0)

    if any(sb.lower() in inst_lower for sb in sb_list): return sb_rate
    if any(std.lower() in inst_lower for std in std_list): return std_rate
    return 0.0

# --- Calculation Helper Function (Uses app.config & contract type) ---
def calculate_contract_totals(contract):
    """ Calculates totals based on contract's scale, updates object (no commit), returns object. """
    app.logger.debug(f"Calculating totals: Contract ID {contract.id}, Local: {contract.applicable_local}, Scale: {contract.applicable_scale}")
    try:
        # --- Get the specific scale config dictionary ---
        scale_config = app.config.get('SCALES', {}).get(contract.applicable_local, {}).get(contract.applicable_scale)
        if not scale_config:
            app.logger.error(f"Scale config not found for {contract.applicable_local} / {contract.applicable_scale}")
            raise ValueError("Scale configuration missing for this contract.") # Raise error

        # Get rates from the loaded scale_config, provide defaults if missing
        base_perf_rate = scale_config.get('PERFORMANCE_BASE', 0.0)
        base_reh_rate = scale_config.get('REHEARSAL_MIN_CALL', 0.0) # Using min call for simplicity
        principal_perf_mult = scale_config.get('PERFORMANCE_PRINCIPAL_PREMIUM', 1.0)
        principal_reh_mult = scale_config.get('REHEARSAL_PRINCIPAL_PREMIUM', 1.0)
        perf_ot_unit_mins = scale_config.get('PERF_OT_UNIT_MINS', 15)
        perf_ot_rate = scale_config.get('PERF_OT_RATE', 0.0)
        perf_ot_principal_rate = scale_config.get('PERF_OT_PRINCIPAL_RATE', 0.0)
        reh_ot_unit_mins = scale_config.get('REH_OT_UNIT_MINS', 30)
        reh_ot_rate = scale_config.get('REH_OT_RATE', 0.0)
        reh_ot_principal_rate = scale_config.get('REH_OT_PRINCIPAL_RATE', 0.0)
        doubling_premium = scale_config.get('DOUBLING_FIRST_PREMIUM', 0.0)
        pension_rate = scale_config.get('PENSION_RATE', 0.0)
        health_perf_rate = scale_config.get('HEALTH_PER_PERFORMANCE', 0.0)
        health_reh_rate = scale_config.get('HEALTH_PER_REHEARSAL', 0.0)
        work_dues_rate = scale_config.get('WORK_DUES_RATE', 0.0)
        # Ensure base rate is usable
        if base_perf_rate <= 0: raise ValueError("Base performance rate is not positive in loaded scale config.")

        perf_hours = contract.actual_hours_engagement or 0; reh_hours = contract.actual_hours_rehearsal or 0
        has_perf = perf_hours > 0; has_reh = contract.has_rehearsal and reh_hours > 0
        app.logger.debug(f" Calc Params - PerfHrs: {perf_hours}, RehHrs: {reh_hours}, HasPerf: {has_perf}, HasReh: {has_reh}")

        total_gross = 0.0; total_pension_contrib = 0.0; total_health_contrib = 0.0; musicians_processed_count = 0

        # --- Leader Calculation ---
        app.logger.debug(f" Calculating leader: {contract.leader_name}")
        leader_is_principal = False # TODO: Determine leader principal status
        leader_doubling = False; leader_cartage = False; leader_instrument = "" # TODO: Add leader flags/instrument
        leader_perf_pay, leader_reh_pay, leader_ot_pay, leader_doubling_pay, leader_cartage_pay = 0.0, 0.0, 0.0, 0.0, 0.0
        if has_perf:
            leader_perf_pay = base_perf_rate;
            if leader_is_principal: leader_perf_pay *= principal_perf_mult
            total_health_contrib += health_perf_rate; app.logger.debug(f"  Ldr Perf Base: {leader_perf_pay:.2f}, Health Add: {health_perf_rate:.2f}")
            if perf_hours > 2.5 and perf_ot_unit_mins > 0: overtime_units = math.ceil(((perf_hours - 2.5) * 60) / perf_ot_unit_mins); ot_rate = perf_ot_principal_rate if leader_is_principal else perf_ot_rate; leader_ot_pay += overtime_units * ot_rate; app.logger.debug(f"  Ldr Perf OT: {overtime_units}u * {ot_rate:.2f} = {leader_ot_pay:.2f}")
        if has_reh:
            leader_reh_pay = base_reh_rate # Using min call rate
            if leader_is_principal: leader_reh_pay *= principal_reh_mult
            total_health_contrib += health_reh_rate; app.logger.debug(f"  Ldr Reh Base: {leader_reh_pay:.2f}, Health Add: {health_reh_rate:.2f}")
            if reh_hours > 2.5 and reh_ot_unit_mins > 0: overtime_reh_units = math.ceil(((reh_hours - 2.5) * 60) / reh_ot_unit_mins); ot_reh_rate = reh_ot_principal_rate if leader_is_principal else reh_ot_rate; reh_ot_amount = overtime_reh_units * ot_reh_rate; leader_ot_pay += reh_ot_amount; app.logger.debug(f"  Ldr Reh OT: {overtime_reh_units}u * {ot_reh_rate:.2f} = {reh_ot_amount:.2f}")
        leader_perf_and_reh_subtotal = leader_perf_pay + leader_reh_pay
        if leader_doubling and leader_perf_and_reh_subtotal > 0: leader_doubling_pay = leader_perf_and_reh_subtotal * doubling_premium; app.logger.debug(f"  Ldr Doubling: +{leader_doubling_pay:.2f}")
        leader_cartage_pay = get_cartage_fee(leader_instrument, leader_cartage, scale_config); # Pass scale_config
        if leader_cartage_pay > 0: app.logger.debug(f"  Ldr Cartage: +{leader_cartage_pay:.2f}")
        leader_gross = leader_perf_pay + leader_reh_pay + leader_ot_pay + leader_doubling_pay + leader_cartage_pay
        app.logger.debug(f"  Leader GROSS calculated: {leader_gross:.2f}")
        if leader_gross > 0: total_gross += leader_gross; total_pension_contrib += leader_gross * pension_rate; musicians_processed_count += 1; app.logger.debug(f"  Leader added totals. Running Gross: {total_gross:.2f}")
        else: app.logger.debug("  Leader Gross is 0.")

        # --- Side Musician Calculations ---
        side_musicians = contract.side_musicians.order_by(SideMusician.id).all()
        app.logger.debug(f"Calculating for {len(side_musicians)} side musicians...")
        for musician in side_musicians:
            app.logger.debug(f"  Musician: {musician.name} (ID: {musician.id}), Inst: {musician.instrument}, Dbl: {musician.is_doubling}, Crt: {musician.has_cartage}");
            musician_is_principal = is_principal(musician.instrument, scale_config) # Pass scale_config
            if musician_is_principal: app.logger.debug(f"    Musician {musician.id} IS Principal")
            perf_pay, reh_pay, ot_pay, doubling_pay, cartage_pay = 0.0, 0.0, 0.0, 0.0, 0.0
            if has_perf:
                perf_pay = base_perf_rate;
                if musician_is_principal: perf_pay *= principal_perf_mult
                total_health_contrib += health_perf_rate; app.logger.debug(f"    Musician {musician.id} Perf Base: {perf_pay:.2f}, Health Add: {health_perf_rate:.2f}")
                if perf_hours > 2.5 and perf_ot_unit_mins > 0: overtime_units = math.ceil(((perf_hours - 2.5) * 60) / perf_ot_unit_mins); ot_rate = perf_ot_principal_rate if musician_is_principal else perf_ot_rate; perf_ot_amount = overtime_units * ot_rate; ot_pay += perf_ot_amount; app.logger.debug(f"    Musician {musician.id} Perf OT: {overtime_units}u * {ot_rate:.2f} = {perf_ot_amount:.2f}")
            if has_reh:
                reh_pay = base_reh_rate # Using min call rate
                if musician_is_principal: reh_pay *= principal_reh_mult
                total_health_contrib += health_reh_rate; app.logger.debug(f"    Musician {musician.id} Reh Base: {reh_pay:.2f}, Health Add: {health_reh_rate:.2f}")
                if reh_hours > 2.5 and reh_ot_unit_mins > 0: overtime_reh_units = math.ceil(((reh_hours - 2.5) * 60) / reh_ot_unit_mins); ot_reh_rate = reh_ot_principal_rate if musician_is_principal else reh_ot_rate; reh_ot_amount = overtime_reh_units * ot_reh_rate; ot_pay += reh_ot_amount; app.logger.debug(f"    Musician {musician.id} Reh OT: {overtime_reh_units}u * {ot_reh_rate:.2f} = {reh_ot_amount:.2f}")
            perf_and_reh_subtotal = perf_pay + reh_pay
            if musician.is_doubling and perf_and_reh_subtotal > 0: doubling_pay = perf_and_reh_subtotal * doubling_premium; app.logger.debug(f"    Musician {musician.id} Doubling: +{doubling_pay:.2f}")
            cartage_pay = get_cartage_fee(musician.instrument, musician.has_cartage, scale_config); # Pass scale_config
            if cartage_pay > 0: app.logger.debug(f"    Musician {musician.id} Cartage: +{cartage_pay:.2f}")
            musician_gross = perf_pay + reh_pay + ot_pay + doubling_pay + cartage_pay
            app.logger.debug(f"    Musician {musician.id} GROSS calculated: {musician_gross:.2f}")
            if musician_gross > 0: total_gross += musician_gross; total_pension_contrib += musician_gross * pension_rate; musicians_processed_count += 1; app.logger.debug(f"    Musician {musician.id} added totals. Running Gross: {total_gross:.2f}")
            else: app.logger.debug(f"    Musician {musician.id} Gross is 0.")

        total_work_dues_contrib = total_gross * work_dues_rate

        # Update Contract object
        contract.total_gross_comp = round(total_gross, 2); contract.total_work_dues = round(total_work_dues_contrib, 2)
        contract.total_pension = round(total_pension_contrib, 2); contract.total_health = round(total_health_contrib, 2)
        contract.num_musicians = musicians_processed_count # Update count based on actual calculation
        app.logger.info(f"Contract {contract.id} Calc Results - Processed: {musicians_processed_count}, Gross: {total_gross:.2f}, Dues: {total_work_dues_contrib:.2f}, Pension: {total_pension_contrib:.2f}, Health: {total_health_contrib:.2f}")
        return contract
    except Exception as e:
        app.logger.error(f"CALCULATION ERROR contract {contract.id}: {e}", exc_info=True)
        contract.total_gross_comp = 0.0; contract.total_work_dues = 0.0 # Reset on error
        contract.total_pension = 0.0; contract.total_health = 0.0
        return contract # Return original object with zeroed totals

# --- Routes (Continued) ---
@app.route('/')
@login_required
def dashboard():
    try: user_contracts = Contract.query.filter_by(user_id=current_user.id).order_by(Contract.last_saved_at.desc()).all(); return render_template('dashboard.html', contracts=user_contracts)
    except Exception as e: app.logger.error(f"Dashboard error user {current_user.email}: {e}", exc_info=True); flash('Could not load dashboard.', 'danger'); return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip(); password = request.form.get('password')
        if not email or not password: flash('Email/password required.', 'danger'); return render_template('register.html')
        if '@' not in email or '.' not in email.split('@')[-1]: flash('Invalid email.', 'danger'); return render_template('register.html')
        if User.query.filter_by(email=email).first(): flash('Email already registered.', 'warning'); return render_template('register.html')
        try: new_user = User(email=email); new_user.set_password(password); db.session.add(new_user); db.session.commit(); login_user(new_user); flash('Registration successful!', 'success'); app.logger.info(f"New user: {email}"); return redirect(url_for('dashboard'))
        except IntegrityError: db.session.rollback(); flash('Email registered (DB).', 'warning'); app.logger.warning(f"Reg IntegrityError: {email}"); return render_template('register.html')
        except Exception as e: db.session.rollback(); flash('Registration error.', 'danger'); app.logger.error(f"Reg error: {e}", exc_info=True); return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip(); password = request.form.get('password')
        if not email or not password: flash('Email/password required.', 'danger'); return render_template('login.html')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember')); flash('Login successful!', 'success'); app.logger.info(f"User logged in: {email}")
            next_page = request.args.get('next');
            if next_page and (next_page.startswith('/') or next_page.startswith(request.host_url)): return redirect(next_page)
            else: return redirect(url_for('dashboard'))
        else: flash('Login failed. Check credentials.', 'danger'); app.logger.warning(f"Failed login: {email}"); return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    if current_user.is_authenticated: app.logger.info(f"User logged out: {current_user.email}"); logout_user(); flash('Logged out.', 'success')
    else: app.logger.warning("Logout route by non-auth user.")
    return redirect(url_for('login'))

# --- Contract Creation/Editing Steps ---
@app.route('/contract/new', methods=['GET'])
@login_required
def new_contract():
    try: new_draft = Contract(user_id=current_user.id, status='draft'); db.session.add(new_draft); db.session.commit(); flash('New draft started.', 'info'); app.logger.info(f"User {current_user.email} started draft {new_draft.id}"); return redirect(url_for('create_contract_step', contract_id=new_draft.id, step_num=1))
    except Exception as e: db.session.rollback(); flash('Failed start new draft.', 'danger'); app.logger.error(f"Error new draft {current_user.email}: {e}", exc_info=True); return redirect(url_for('dashboard'))

@app.route('/contract/create/<int:contract_id>/step/<int:step_num>', methods=['GET', 'POST'])
@login_required
def create_contract_step(contract_id, step_num):
    try: contract = db.session.get(Contract, contract_id);
    except Exception as e: app.logger.error(f"Error fetching contract {contract_id}: {e}", exc_info=True); flash('Error loading contract.', 'danger'); return redirect(url_for('dashboard'))
    if not contract or contract.user_id != current_user.id: flash('Contract not found/permission denied.', 'danger'); app.logger.warning(f"User {current_user.email} invalid access: contract {contract_id}"); return redirect(url_for('dashboard'))

    if contract.status == 'completed' and request.method == 'POST': flash('Completed contract. Reopen to edit.', 'warning'); return redirect(url_for('view_contract', contract_id=contract.id))

    if request.method == 'POST':
        is_saving_draft = 'save_draft' in request.form
        try:
            if step_num == 1: # Step 1 Processing
                contract.engagement_date = parse_date_safe(request.form.get('engagement_date')); contract.leader_name = request.form.get('leader_name', '').strip()
                contract.leader_card_no = request.form.get('leader_card_no', '').strip(); contract.leader_ssn_ein = request.form.get('leader_ssn_ein', '').strip()
                contract.leader_address = request.form.get('leader_address', '').strip(); contract.leader_phone = request.form.get('leader_phone', '').strip()
                contract.band_name = request.form.get('band_name', '').strip(); contract.venue_name = request.form.get('venue_name', '').strip()
                contract.location_borough = request.form.get('location_borough'); contract.engagement_type = request.form.get('engagement_type', '').strip()
                contract.start_time = parse_time_safe(request.form.get('start_time')); contract.end_time = parse_time_safe(request.form.get('end_time'))
                contract.pre_heat_hours = parse_float_safe(request.form.get('pre_heat_hours'))
                # TODO: Add input field for selecting applicable_local and applicable_scale
                # contract.applicable_local = request.form.get('applicable_local', 'Local802')
                # contract.applicable_scale = request.form.get('applicable_scale', 'ClassicalConcert_23_24')
                errors = []; # Validation
                if not contract.engagement_date: errors.append("Date required.")
                if not contract.leader_name: errors.append("Leader name required.") # etc...
                if errors:
                    for error in errors: flash(error, 'danger')
                    return render_template(f'create_contract_step{step_num}.html', contract=contract, step_num=step_num)
                contract = calculate_contract_totals(contract); db.session.commit() # Calc & Commit
                if is_saving_draft: flash('Draft saved.', 'success'); app.logger.info(f"Contract {contract_id} Step 1 draft saved by {current_user.email}"); return redirect(url_for('dashboard'))
                flash('Step 1 saved.', 'success'); app.logger.info(f"Contract {contract_id} Step 1 saved, proceed step 2 by {current_user.email}"); return redirect(url_for('create_contract_step', contract_id=contract_id, step_num=2))

            elif step_num == 2: # Step 2 Processing
                try: contract.num_musicians = max(1, int(request.form.get('num_musicians', 1)))
                except ValueError: contract.num_musicians = 1; flash("Invalid musician count.", "warning")
                contract.has_rehearsal = 'has_rehearsal' in request.form; contract.actual_hours_engagement = parse_float_safe(request.form.get('actual_hours_engagement'))
                contract.is_recorded = 'is_recorded' in request.form; contract.leader_is_incorporated = 'leader_is_incorporated' in request.form
                errors = []; # Validation
                if contract.actual_hours_engagement is None or contract.actual_hours_engagement <= 0: errors.append("Valid engagement hours required.")
                if contract.has_rehearsal:
                    contract.actual_hours_rehearsal = parse_float_safe(request.form.get('actual_hours_rehearsal'))
                    if contract.actual_hours_rehearsal is None or contract.actual_hours_rehearsal <= 0: errors.append("Valid rehearsal hours required if checked.")
                else: contract.actual_hours_rehearsal = None
                # Process Side Musicians
                SideMusician.query.filter_by(contract_id=contract.id).delete() # Delete old
                new_side_musicians = []
                for i in range(contract.num_musicians - 1):
                    prefix = f"musician-{i}-"; name = request.form.get(prefix + "name", "").strip(); tax_id_value = request.form.get(prefix + "tax_id", "").strip() # Use tax_id
                    card_no = request.form.get(prefix + "card_no", "").strip(); instrument = request.form.get(prefix + "instrument", "").strip()
                    is_doubling = prefix + "is_doubling" in request.form; has_cartage = prefix + "has_cartage" in request.form
                    m_num = i + 1
                    if not name: errors.append(f"Name required for Side Musician #{m_num}.")
                    if not tax_id_value: errors.append(f"Tax ID required for Side Musician #{m_num} ({name or 'Unnamed'}).") # Use tax_id
                    if not errors: new_side_musicians.append(SideMusician(contract_id=contract.id, name=name, tax_id=tax_id_value, card_no=card_no, instrument=instrument, is_doubling=is_doubling, has_cartage=has_cartage)) # Use tax_id
                    else: app.logger.warning(f"Validation error side musician #{m_num} on contract {contract.id}")

                if errors:
                    for error in errors: flash(error, 'danger')
                    app.logger.warning(f"Validation errors saving Step 2 for contract {contract.id}")
                    musicians_data_on_error = [{'name': request.form.get(f"musician-{i}-name",''), 'tax_id': request.form.get(f"musician-{i}-tax_id",''), 'card_no': request.form.get(f"musician-{i}-card_no",''), 'instrument': request.form.get(f"musician-{i}-instrument",''), 'is_doubling': f"musician-{i}-is_doubling" in request.form, 'has_cartage': f"musician-{i}-has_cartage" in request.form} for i in range(contract.num_musicians - 1)] # Use tax_id
                    return render_template(f'create_contract_step{step_num}.html', contract=contract, step_num=step_num, musicians_json=musicians_data_on_error)

                db.session.add_all(new_side_musicians); # Add valid musicians
                contract = calculate_contract_totals(contract) # Recalculate AFTER saving musicians
                db.session.commit() # Commit changes including side musicians and calculated totals

                if is_saving_draft: flash('Draft saved.', 'success'); app.logger.info(f"Contract {contract_id} Step 2 draft saved by {current_user.email}"); return redirect(url_for('dashboard'))
                flash('Step 2 data saved.', 'success'); app.logger.info(f"Contract {contract_id} Step 2 saved by {current_user.email}, redirecting view."); return redirect(url_for('view_contract', contract_id=contract.id))

            else: flash(f"Invalid step: {step_num}", "danger"); app.logger.error(f"Invalid step POST {step_num} for contract {contract_id}"); return redirect(url_for('dashboard'))
        except Exception as e: db.session.rollback(); flash(f'Unexpected error saving step {step_num}.', 'danger'); app.logger.error(f"Error saving contract {contract_id} step {step_num} for {current_user.email}: {e}", exc_info=True); return render_template(f'create_contract_step{step_num}.html', contract=contract, step_num=step_num)

    # --- Handle GET request ---
    template_name = f'create_contract_step{step_num}.html'; template_path = os.path.join(app.template_folder, template_name)
    if not os.path.exists(template_path): flash(f"Form step {step_num} not found.", "danger"); app.logger.error(f"Template not found: {template_path}"); return redirect(url_for('dashboard') if step_num > 1 else url_for('create_contract_step', contract_id=contract.id, step_num=1))
    musicians_data = []
    if step_num == 2:
        try:
            musicians = contract.side_musicians.order_by(SideMusician.id).all()
            for m in musicians: musicians_data.append({'name': m.name, 'tax_id': m.tax_id, 'card_no': m.card_no, 'instrument': m.instrument, 'is_doubling': m.is_doubling, 'has_cartage': m.has_cartage}) # Use tax_id
            app.logger.debug(f"Passing {len(musicians_data)} existing musicians for contract {contract_id}")
        except Exception as e: app.logger.error(f"Error fetching musicians for contract {contract_id} on GET: {e}", exc_info=True); flash("Could not load musician data.", "warning")
    return render_template(template_name, contract=contract, step_num=step_num, musicians_json=musicians_data)


@app.route('/contract/view/<int:contract_id>')
@login_required
def view_contract(contract_id):
    try: contract = db.session.get(Contract, contract_id);
    except Exception as e: app.logger.error(f"Error fetching contract {contract_id} for view: {e}", exc_info=True); flash('Error loading contract.', 'danger'); return redirect(url_for('dashboard'))
    if not contract or contract.user_id != current_user.id: flash('Contract not found/access denied.', 'danger'); return redirect(url_for('dashboard'))
    musicians = contract.side_musicians.order_by(SideMusician.id).all()
    return render_template('view_contract.html', contract=contract, musicians=musicians)


# --- Contract Action Routes ---
@app.route('/contract/delete/<int:contract_id>', methods=['POST'])
@login_required
def delete_contract(contract_id):
    try: c = db.session.get(Contract, contract_id);
    except Exception as e: app.logger.error(f"Error fetching contract {contract_id} for delete: {e}", exc_info=True); flash('Error deleting.', 'danger'); return redirect(url_for('dashboard'))
    if not c or c.user_id != current_user.id: flash('Cannot delete: Not found/permission denied.', 'danger'); app.logger.warning(f"User {current_user.email} failed delete: {contract_id}"); return redirect(url_for('dashboard'))
    info = f"ID {c.id} ({c.engagement_date or 'No Date'})"; db.session.delete(c); db.session.commit(); flash(f"Contract deleted: {info}", 'success'); app.logger.info(f"User {current_user.email} deleted {contract_id}")
    return redirect(url_for('dashboard'))

@app.route('/contract/reopen/<int:contract_id>', methods=['POST'])
@login_required
def reopen_contract(contract_id):
    try: c = db.session.get(Contract, contract_id);
    except Exception as e: app.logger.error(f"Error fetching contract {contract_id} for reopen: {e}", exc_info=True); flash('Error reopening.', 'danger'); return redirect(url_for('dashboard'))
    if not c or c.user_id != current_user.id: flash('Cannot reopen: Not found/permission denied.', 'danger'); app.logger.warning(f"User {current_user.email} failed reopen: {contract_id}"); return redirect(url_for('dashboard'))
    if c.status != 'completed': flash('Only completed contracts can be reopened.', 'warning'); return redirect(url_for('view_contract', contract_id=contract_id))
    c.status = 'draft'; db.session.commit(); flash(f"Contract reopened for editing.", 'success'); app.logger.info(f"User {current_user.email} reopened {contract_id}")
    return redirect(url_for('create_contract_step', contract_id=contract_id, step_num=1))

@app.route('/contract/finalize/<int:contract_id>', methods=['POST'])
@login_required
def finalize_contract(contract_id):
    """Marks a draft contract as completed. Assumes calculations are up-to-date."""
    try:
        contract = db.session.get(Contract, contract_id)
        if not contract or contract.user_id != current_user.id: flash('Cannot finalize: Not found/permission denied.', 'danger'); app.logger.warning(f"User {current_user.email} failed finalize: {contract_id}"); return redirect(url_for('dashboard'))
        if contract.status != 'draft': flash('Only draft contracts can be finalized.', 'warning'); return redirect(url_for('view_contract', contract_id=contract_id))

        # Optional: Recalculate here as a final safety check?
        # contract = calculate_contract_totals(contract)
        # app.logger.info(f"Final check calculation run for contract {contract_id}")

        contract.status = 'completed'; db.session.commit() # Commit final status
        flash(f"Contract successfully finalized!", 'success'); app.logger.info(f"User {current_user.email} finalized contract {contract_id}")
        return redirect(url_for('view_contract', contract_id=contract.id)) # Show finalized view

    except Exception as e: db.session.rollback(); flash('Error finalizing contract.', 'danger'); app.logger.error(f"Error finalizing contract {contract_id} for {current_user.email}: {e}", exc_info=True)
    return redirect(url_for('view_contract', contract_id=contract_id)) # Redirect back to view


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e): app.logger.warning(f"404: {request.url} - {e}"); return render_template('404.html'), 404 if os.path.exists(os.path.join(app.template_folder, '404.html')) else ("<h1>404</h1>", 404)
@app.errorhandler(500)
def internal_server_error(e):
    try: db.session.rollback()
    except Exception as rb_exc: app.logger.error(f"Rollback error after 500: {rb_exc}", exc_info=True)
    app.logger.error(f"500: {e}", exc_info=True); return render_template('500.html'), 500 if os.path.exists(os.path.join(app.template_folder, '500.html')) else ("<h1>500</h1>", 500)
@app.errorhandler(403)
def forbidden_error(e): user = current_user.email if current_user.is_authenticated else 'anon'; app.logger.warning(f"403: {request.url} by {user}"); flash("Access Denied.", "warning"); return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))
@app.errorhandler(401)
def unauthorized_error(e): app.logger.warning(f"401: {request.url}"); flash("Login required.", "info"); return redirect(url_for('login', next=request.url))


# --- Database Initialization ---
def initialize_database():
    with app.app_context():
        instance_path = app.instance_path; db_uri = app.config['SQLALCHEMY_DATABASE_URI']; is_sqlite = db_uri.startswith('sqlite:')
        app.logger.info(f"DB Init. URI: {db_uri}")
        if is_sqlite:
            db_file_path = db_uri.split('sqlite:///')[-1]
            if not os.path.isabs(db_file_path): db_file_path = os.path.join(instance_path, db_file_path)
            db_dir = os.path.dirname(db_file_path)
            if not os.path.exists(db_dir):
                 try: os.makedirs(db_dir); app.logger.info(f"Created DB directory: {db_dir}")
                 except OSError as e: app.logger.critical(f"CRITICAL: Failed create DB dir {db_dir}: {e}"); return
        try: app.logger.info("Calling db.create_all()"); db.create_all(); app.logger.info("db.create_all() finished.")
        except Exception as e: app.logger.critical(f"CRITICAL: DB creation failed: {e}", exc_info=True) # raise e

with app.app_context():
    initialize_database()

# --- Main Execution Block ---
if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    try: port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    except ValueError: port = 5000; app.logger.warning(f"Invalid FLASK_RUN_PORT, using {port}")
    use_debugger = app.config.get('DEBUG', False)
    app.run(host=host, port=port, debug=use_debugger)
