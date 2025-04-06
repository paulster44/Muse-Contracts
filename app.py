# app.py
import os
import datetime
import logging
import math
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response # Added make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from flask_weasyprint import HTML # <<< PDF import UNCOMMENTED
from models import db, User, Contract, SideMusician # Ensure models.py is correct
from sqlalchemy.exc import IntegrityError
# --- WTForms Imports ---
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, TimeField, FloatField, SelectField, SubmitField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError # Added ValidationError

# Load environment variables from .env file
load_dotenv()

# Create Flask app instance
app = Flask(__name__, instance_relative_config=True)

# --- Load Configuration ---
try:
    app.config.from_object('config') # Load defaults from config.py
except ImportError:
    app.logger.error("FATAL: config.py not found. Cannot start.")
    exit() # Exit if main config is missing
except Exception as e:
     app.logger.error(f"FATAL: Error loading config.py: {e}")
     exit()

# Ensure the instance folder exists
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

# --- FORMS ---
class ContractStep1Form(FlaskForm):
    engagement_date = DateField('Engagement Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()], format='%H:%M')
    end_time = TimeField('End Time', validators=[DataRequired()], format='%H:%M')
    leader_name = StringField('Leader/Employer Name', validators=[DataRequired(), Length(max=150)])
    leader_card_no = StringField('Leader AFM Card No.', validators=[Optional(), Length(max=50)])
    leader_address = StringField('Leader/Employer Address', validators=[DataRequired(), Length(max=250)])
    leader_phone = StringField('Leader/Employer Phone', validators=[DataRequired(), Length(max=30)])
    leader_ssn_ein = StringField('Leader SSN or EIN', validators=[Optional(), Length(max=50)])
    band_name = StringField('Name of Band/Group', validators=[Optional(), Length(max=150)])
    venue_name = StringField('Place of Engagement (Venue/Room)', validators=[DataRequired(), Length(max=200)])
    location_borough = SelectField('Location (Borough/Area)', choices=[('', '-- Choose --'),('NYC', 'NYC (Manhattan)'), ('BKLYN', 'Brooklyn'), ('QNS', 'Queens'), ('BX', 'Bronx'), ('SI', 'Staten Island'), ('NAS_SUF', 'Nassau/Suffolk'), ('OOT', 'Out of Town')], validators=[DataRequired(message="Please select a location.")])
    engagement_type = StringField('Type of Engagement', validators=[DataRequired(), Length(max=200)], render_kw={"placeholder": "e.g., Wedding, Concert"})
    pre_heat_hours = FloatField('Pre-Heat Hours', validators=[Optional(), NumberRange(min=0, message="Hours must be non-negative.")])
    save_draft = SubmitField('Save Draft & Exit')
    submit_next = SubmitField('Save and Continue »')

class ContractStep2Form(FlaskForm):
    num_musicians = IntegerField('Total Number of Musicians (incl. Leader)', validators=[DataRequired(), NumberRange(min=1)], default=1)
    actual_hours_engagement = FloatField('Actual Paid Hours of Engagement', validators=[DataRequired(message="Engagement hours required."), NumberRange(min=0.1)])
    has_rehearsal = BooleanField('Is there a Rehearsal?')
    actual_hours_rehearsal = FloatField('Actual Paid Hours of Rehearsal', validators=[Optional(), NumberRange(min=0.1)])
    is_recorded = BooleanField('Will performance be Recorded/Reproduced/Transmitted?')
    leader_is_incorporated = BooleanField('Is the Leader/Employer signing as an incorporated entity?')
    save_draft = SubmitField('Save Draft & Exit')
    submit_view = SubmitField('Save Step 2 & View »')
    def validate_actual_hours_rehearsal(form, field):
        if form.has_rehearsal.data and (field.data is None or field.data <= 0):
            raise ValidationError('Rehearsal hours required & positive if checked.')
# --- END FORMS ---


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
def is_principal(instrument_string, scale_config):
    if not instrument_string or not scale_config: return False
    principal_list = scale_config.get('PRINCIPAL_INSTRUMENTS', [])
    if not principal_list: app.logger.warning("PRINCIPAL_INSTRUMENTS list empty."); return False
    return any(p.lower() in instrument_string.lower() for p in principal_list)
def get_cartage_fee(instrument_string, has_cartage_flag, scale_config):
    if not has_cartage_flag or not instrument_string or not scale_config: return 0.0
    inst_lower = instrument_string.lower()
    sb_list = scale_config.get('CARTAGE_INSTRUMENTS_SB', []); std_list = scale_config.get('CARTAGE_INSTRUMENTS_STD', [])
    if any(sb.lower() in inst_lower for sb in sb_list): return app.config.get('SCALE_CARTAGE_STRING_BASS', 0.0)
    if any(std.lower() in inst_lower for std in std_list): return app.config.get('SCALE_CARTAGE_CELLO_BASS_ETC', 0.0)
    return 0.0

# --- Calculation Helper Function ---
def calculate_contract_totals(contract):
    # (Calculation logic remains the same as last version)
    app.logger.debug(f"Calculating totals: Contract ID {contract.id}, Local: {contract.applicable_local}, Scale: {contract.applicable_scale}")
    try:
        scale_config = app.config.get('SCALES', {}).get(contract.applicable_local, {}).get(contract.applicable_scale)
        if not scale_config: raise ValueError("Scale configuration missing for this contract.")
        base_perf_rate = scale_config.get('PERFORMANCE_BASE', 0.0); base_reh_rate = scale_config.get('REHEARSAL_MIN_CALL', 0.0)
        principal_perf_mult = scale_config.get('PERFORMANCE_PRINCIPAL_PREMIUM', 1.0); principal_reh_mult = scale_config.get('REHEARSAL_PRINCIPAL_PREMIUM', 1.0)
        perf_ot_unit_mins = scale_config.get('PERF_OT_UNIT_MINS', 15); perf_ot_rate = scale_config.get('PERF_OT_RATE', 0.0)
        perf_ot_principal_rate = scale_config.get('PERF_OT_PRINCIPAL_RATE', 0.0); reh_ot_unit_mins = scale_config.get('REH_OT_UNIT_MINS', 30)
        reh_ot_rate = scale_config.get('REH_OT_RATE', 0.0); reh_ot_principal_rate = scale_config.get('REH_OT_PRINCIPAL_RATE', 0.0)
        doubling_premium = scale_config.get('DOUBLING_FIRST_PREMIUM', 0.0); pension_rate = scale_config.get('PENSION_RATE', 0.0)
        health_perf_rate = scale_config.get('HEALTH_PER_PERFORMANCE', 0.0); health_reh_rate = scale_config.get('HEALTH_PER_REHEARSAL', 0.0)
        work_dues_rate = scale_config.get('WORK_DUES_RATE', 0.0)
        if base_perf_rate <= 0: raise ValueError("Base performance rate not positive.")

        perf_hours = contract.actual_hours_engagement or 0; reh_hours = contract.actual_hours_rehearsal or 0
        has_perf = perf_hours > 0; has_reh = contract.has_rehearsal and reh_hours > 0
        app.logger.debug(f" Calc Params - PerfHrs: {perf_hours}, RehHrs: {reh_hours}, HasPerf: {has_perf}, HasReh: {has_reh}")

        total_gross = 0.0; total_pension_contrib = 0.0; total_health_contrib = 0.0; musicians_processed_count = 0

        # Leader Calculation
        leader_is_principal = False; leader_doubling = False; leader_cartage = False; leader_instrument = "" # TODO: Leader flags
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

        # Side Musician Calculations
        side_musicians = contract.side_musicians.order_by(SideMusician.id).all()
        app.logger.debug(f"Calculating for {len(side_musicians)} side musicians...")
        for musician in side_musicians:
            app.logger.debug(f"  Musician: {musician.name} (ID: {musician.id}), Inst: {musician.instrument}, Dbl: {musician.is_doubling}, Crt: {musician.has_cartage}"); musician_is_principal = is_principal(musician.instrument, scale_config) # Pass scale_config
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
        contract.total_gross_comp = 0.0; contract.total_work_dues = 0.0; contract.total_pension = 0.0; contract.total_health = 0.0
        return contract

# --- Routes ---
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

# >>>>> CORRECTED new_contract ROUTE with explicit endpoint name <<<<<
@app.route('/contract/new', methods=['GET'], endpoint='new_contract_route') # Explicit endpoint
@login_required
def new_contract():
    """Starts a new contract draft."""
    try: new_draft = Contract(user_id=current_user.id, status='draft'); db.session.add(new_draft); db.session.commit(); flash('New draft started.', 'info'); app.logger.info(f"User {current_user.email} started draft {new_draft.id}"); return redirect(url_for('create_contract_step', contract_id=new_draft.id, step_num=1))
    except Exception as e: db.session.rollback(); flash('Failed start new draft.', 'danger'); app.logger.error(f"Error new draft {current_user.email}: {e}", exc_info=True); return redirect(url_for('dashboard'))
# >>>>> END new_contract ROUTE <<<<<


@app.route('/contract/create/<int:contract_id>/step/<int:step_num>', methods=['GET', 'POST'])
@login_required
def create_contract_step(contract_id, step_num):
    """Handles the multi-step contract form (editing drafts)."""
    try: contract = db.session.get(Contract, contract_id);
    except Exception as e: app.logger.error(f"Error fetching contract {contract_id}: {e}", exc_info=True); flash('Error loading contract.', 'danger'); return redirect(url_for('dashboard'))
    if not contract or contract.user_id != current_user.id: flash('Contract not found/permission denied.', 'danger'); app.logger.warning(f"User {current_user.email} invalid access: contract {contract_id}"); return redirect(url_for('dashboard'))

    if contract.status == 'completed' and request.method == 'POST': flash('Completed contract. Reopen to edit.', 'warning'); return redirect(url_for('view_contract', contract_id=contract.id))

    form = None
    if step_num == 1: form = ContractStep1Form(request.form if request.method == 'POST' else None, obj=contract)
    elif step_num == 2: form = ContractStep2Form(request.form if request.method == 'POST' else None, obj=contract)
    else: flash(f"Invalid step number: {step_num}", "danger"); return redirect(url_for('dashboard'))

    if form.validate_on_submit():
        is_saving_draft = form.save_draft.data if hasattr(form, 'save_draft') else False
        try:
            form.populate_obj(contract) # Populate main fields from WTForm

            if step_num == 1:
                contract = calculate_contract_totals(contract); db.session.commit()
                if is_saving_draft: flash('Draft saved.', 'success'); return redirect(url_for('dashboard'))
                flash('Step 1 saved.', 'success'); return redirect(url_for('create_contract_step', contract_id=contract_id, step_num=2))

            elif step_num == 2:
                errors = []; SideMusician.query.filter_by(contract_id=contract.id).delete(); new_side_musicians = []
                num_musicians_from_form = form.num_musicians.data or 1
                for i in range(num_musicians_from_form - 1):
                    prefix = f"musician-{i}-"; name = request.form.get(prefix + "name", "").strip(); tax_id_value = request.form.get(prefix + "tax_id", "").strip()
                    card_no = request.form.get(prefix + "card_no", "").strip(); instrument = request.form.get(prefix + "instrument", "").strip()
                    is_doubling = prefix + "is_doubling" in request.form; has_cartage = prefix + "has_cartage" in request.form
                    m_num = i + 1
                    if not name: errors.append(f"Name required for Side Musician #{m_num}.")
                    # Tax ID optional per previous change
                    if not errors: new_side_musicians.append(SideMusician(contract_id=contract.id, name=name, tax_id=tax_id_value or None, card_no=card_no, instrument=instrument, is_doubling=is_doubling, has_cartage=has_cartage))
                    else: app.logger.warning(f"Validation error prevented add for side musician #{m_num}")

                if errors: # Re-render form with errors
                    for error in errors: flash(error, 'danger')
                    musicians_data_on_error = [{'name': request.form.get(f"musician-{i}-name",''), 'tax_id': request.form.get(f"musician-{i}-tax_id",''), 'card_no': request.form.get(f"musician-{i}-card_no",''), 'instrument': request.form.get(f"musician-{i}-instrument",''), 'is_doubling': f"musician-{i}-is_doubling" in request.form, 'has_cartage': f"musician-{i}-has_cartage" in request.form} for i in range(num_musicians_from_form - 1)]
                    return render_template(f'create_contract_step{step_num}.html', contract=contract, step_num=step_num, form=form, musicians_json=musicians_data_on_error)

                db.session.add_all(new_side_musicians);
                contract = calculate_contract_totals(contract); db.session.commit()
                if is_saving_draft: flash('Draft saved.', 'success'); return redirect(url_for('dashboard'))
                flash('Step 2 data saved.', 'success'); return redirect(url_for('view_contract', contract_id=contract.id))

            else: flash(f"Invalid step POST: {step_num}", "danger"); return redirect(url_for('dashboard'))

        except Exception as e: db.session.rollback(); flash(f'Error saving step {step_num}.', 'danger'); app.logger.error(f"Error save POST step {step_num} for {contract_id}: {e}", exc_info=True)
        # Fall through to render template with WTForm errors if exception occurred after validation

    # --- Handle GET request OR WTForms POST validation failure ---
    template_name = f'create_contract_step{step_num}.html'; template_path = os.path.join(app.template_folder, template_name)
    if not os.path.exists(template_path): flash(f"Form step {step_num} not found.", "danger"); app.logger.error(f"Template not found: {template_path}"); return redirect(url_for('dashboard') if step_num > 1 else url_for('create_contract_step', contract_id=contract.id, step_num=1))
    musicians_data = []
    # Fetch existing musicians ONLY for Step 2 GET for pre-population
    if step_num == 2 and request.method == 'GET':
        try:
            musicians = contract.side_musicians.order_by(SideMusician.id).all()
            for m in musicians: musicians_data.append({'name': m.name, 'tax_id': m.tax_id, 'card_no': m.card_no, 'instrument': m.instrument, 'is_doubling': m.is_doubling, 'has_cartage': m.has_cartage})
            app.logger.debug(f"Passing {len(musicians_data)} existing musicians on GET for contract {contract_id}")
        except Exception as e: app.logger.error(f"Error fetching musicians for contract {contract_id} on GET: {e}", exc_info=True); flash("Could not load musician data.", "warning")

    # Pass form object (contains data/errors if POST failed validation)
    return render_template(template_name, contract=contract, step_num=step_num, form=form, musicians_json=musicians_data)


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
        # Final check calculation (optional, but good practice)
        contract = calculate_contract_totals(contract)
        app.logger.info(f"Final check calculation run for contract {contract_id}")
        contract.status = 'completed'; db.session.commit()
        flash(f"Contract successfully finalized!", 'success'); app.logger.info(f"User {current_user.email} finalized contract {contract_id}")
        return redirect(url_for('view_contract', contract_id=contract.id))
    except Exception as e: db.session.rollback(); flash('Error finalizing contract.', 'danger'); app.logger.error(f"Error finalizing contract {contract_id} for {current_user.email}: {e}", exc_info=True)
    return redirect(url_for('view_contract', contract_id=contract_id))


# --- PDF Generation Route (UNCOMMENTED) ---
@app.route('/contract/pdf/<int:contract_id>')
@login_required
def download_contract_pdf(contract_id):
    """Generates a PDF version of the contract."""
    try:
        contract = db.session.get(Contract, contract_id)
        if not contract or contract.user_id != current_user.id: flash('Contract not found or access denied.', 'danger'); return redirect(url_for('dashboard'))
        musicians = contract.side_musicians.order_by(SideMusician.id).all()
        scale_config = app.config.get('SCALES', {}).get(contract.applicable_local, {}).get(contract.applicable_scale)
        pension_rate_config = scale_config.get('PENSION_RATE', 0.0) if scale_config else 0.0
        html = render_template('contract_pdf.html', contract=contract, musicians=musicians, pension_rate_percent=pension_rate_config * 100)
        html_obj = HTML(string=html, base_url=request.base_url); pdf = html_obj.write_pdf()
        response = make_response(pdf); response.headers['Content-Type'] = 'application/pdf'
        filename = f"AFM802_Contract_{contract.id}_{contract.engagement_date or 'nodate'}.pdf"
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        app.logger.info(f"User {current_user.email} generated PDF for contract {contract_id}"); return response
    except NameError as ne: app.logger.error(f"PDF Gen Error - Missing Import: {ne}", exc_info=True); flash('PDF generation library not available.', 'danger'); return redirect(url_for('view_contract', contract_id=contract_id))
    except Exception as e: app.logger.error(f"Error generating PDF for {contract_id}: {e}", exc_info=True); flash('Error generating PDF.', 'danger'); return redirect(url_for('view_contract', contract_id=contract_id))


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
            db_file_path = db_uri.split('sqlite:///')[-1];
            if not os.path.isabs(db_file_path): db_file_path = os.path.join(instance_path, db_file_path)
            db_dir = os.path.dirname(db_file_path)
            if not os.path.exists(db_dir):
                 try: os.makedirs(db_dir); app.logger.info(f"Created DB directory: {db_dir}")
                 except OSError as e: app.logger.critical(f"CRITICAL: Failed create DB dir {db_dir}: {e}"); return
        try: app.logger.info("Calling db.create_all()"); db.create_all(); app.logger.info("db.create_all() finished.")
        except Exception as e: app.logger.critical(f"CRITICAL: DB creation failed: {e}", exc_info=True)

with app.app_context():
    initialize_database()

# --- Main Execution Block ---
if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    try: port = int(os.environ.get('FLASK_RUN_PORT', '5001')) # Default to 5001
    except ValueError: port = 5001; app.logger.warning(f"Invalid FLASK_RUN_PORT, using {port}")
    use_debugger = app.config.get('DEBUG', False)
    app.run(host=host, port=port, debug=use_debugger)
