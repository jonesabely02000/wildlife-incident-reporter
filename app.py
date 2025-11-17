import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import logging
import csv
from io import StringIO
from collections import Counter
import secrets
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration - FIXED FOR PERSISTENT SESSIONS
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Extended to 30 days
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# Database Models - UPDATED FOR PASSWORD RECOVERY
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    verified = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Password recovery fields
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    species = db.Column(db.String(100), nullable=False)
    incident_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    reported_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Backup/Restore system for database persistence
class DataBackup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    backup_type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper Functions
def get_current_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            # Update last login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            return user
    return None

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash('Please login first', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def create_backup():
    """Create backup of important data"""
    try:
        # Backup users
        users = User.query.all()
        users_data = []
        for user in users:
            users_data.append({
                'email': user.email,
                'password': user.password,
                'verified': user.verified,
                'created_at': user.created_at.isoformat()
            })
        
        # Backup incidents
        incidents = Incident.query.all()
        incidents_data = []
        for incident in incidents:
            incidents_data.append({
                'date': incident.date.isoformat(),
                'latitude': incident.latitude,
                'longitude': incident.longitude,
                'species': incident.species,
                'incident_type': incident.incident_type,
                'severity': incident.severity,
                'description': incident.description,
                'reported_by': incident.reported_by,
                'created_at': incident.created_at.isoformat()
            })
        
        # Save backups
        user_backup = DataBackup(backup_type='users', data=str(users_data))
        incident_backup = DataBackup(backup_type='incidents', data=str(incidents_data))
        
        db.session.add(user_backup)
        db.session.add(incident_backup)
        db.session.commit()
        
        logger.info("Backup created successfully")
        return True
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return False

def restore_from_backup():
    """Restore data from backup if database was reset"""
    try:
        # Check if we need to restore
        user_count = User.query.count()
        incident_count = Incident.query.count()
        
        if user_count > 0 and incident_count > 0:
            return True  # No restoration needed
            
        latest_users_backup = DataBackup.query.filter_by(backup_type='users').order_by(DataBackup.created_at.desc()).first()
        latest_incidents_backup = DataBackup.query.filter_by(backup_type='incidents').order_by(DataBackup.created_at.desc()).first()
        
        if latest_users_backup:
            # Restore users
            users_data = eval(latest_users_backup.data)
            for user_data in users_data:
                if not User.query.filter_by(email=user_data['email']).first():
                    user = User(
                        email=user_data['email'],
                        password=user_data['password'],
                        verified=user_data['verified'],
                        created_at=datetime.fromisoformat(user_data['created_at'])
                    )
                    db.session.add(user)
            
        if latest_incidents_backup:
            # Restore incidents
            incidents_data = eval(latest_incidents_backup.data)
            for incident_data in incidents_data:
                incident = Incident(
                    date=datetime.fromisoformat(incident_data['date']),
                    latitude=incident_data['latitude'],
                    longitude=incident_data['longitude'],
                    species=incident_data['species'],
                    incident_type=incident_data['incident_type'],
                    severity=incident_data['severity'],
                    description=incident_data['description'],
                    reported_by=incident_data['reported_by'],
                    created_at=datetime.fromisoformat(incident_data['created_at'])
                )
                db.session.add(incident)
        
        db.session.commit()
        logger.info("Data restored from backup successfully")
        return True
    except Exception as e:
        logger.error(f"Restoration failed: {str(e)}")
        return False

def init_db():
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Restore from backup if needed
            restore_from_backup()
            
            # Create guest user if doesn't exist
            guest_email = "guest@wildlife.com"
            if not User.query.filter_by(email=guest_email).first():
                guest_user = User(email=guest_email, password="guest123", verified=True)
                db.session.add(guest_user)
                db.session.commit()
                logger.info("Guest user created successfully")
            
            # Create backup
            create_backup()
                
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")

def get_all_incidents():
    """Get all incidents for team collaboration"""
    return Incident.query.order_by(Incident.date.desc()).all()

def get_user_incidents(user):
    """Get incidents for specific user"""
    return Incident.query.filter_by(reported_by=user.email).order_by(Incident.date.desc()).all()

# Routes
@app.before_request
def before_request():
    """Create session and backup before each request"""
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=30)
    
    # Create backup periodically (every 100 requests or so)
    if hasattr(app, 'request_count'):
        app.request_count += 1
    else:
        app.request_count = 1
        
    if app.request_count % 100 == 0:
        create_backup()

@app.route('/')
def index():
    user = get_current_user()
    return render_template('home.html', user=user)

@app.route('/home')
def home():
    user = get_current_user()
    return render_template('home.html', user=user)

@app.route('/view-incidents')
@login_required
def view_incidents():
    try:
        user = get_current_user()
        incidents = get_user_incidents(user)
        return render_template('incidents.html', user=user, incidents=incidents)
    except Exception as e:
        logger.error(f"Error in view_incidents: {str(e)}")
        flash('Error loading incidents. Please try again.', 'error')
        return redirect(url_for('home'))

@app.route('/report-incident')
@login_required
def report_incident():
    user = get_current_user()
    return render_template('report.html', user=user)

@app.route('/predictions')
@login_required
def predictions():
    user = get_current_user()
    return render_template('predictions.html', user=user)

# Enhanced Auth Routes with Password Recovery
@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_user():
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['user_email'] = user.email
            session.permanent = True
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash('Login successful!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if get_current_user():
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not email or not password:
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if len(password) < 3:
            flash('Password must be at least 3 characters', 'error')
            return render_template('register.html')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        try:
            user = User(email=email, password=password, verified=True)
            db.session.add(user)
            db.session.commit()
            
            session['user_id'] = user.id
            session['user_email'] = user.email
            session.permanent = True
            
            # Create backup after new registration
            create_backup()
            
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

# PASSWORD RECOVERY ROUTES
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if get_current_user():
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        
        if user:
            # In a real app, you would send an email here
            # For this demo, we'll just show the password
            flash(f'Password for {email}: {user.password}', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email not found', 'error')
    
    return render_template('forgot_password.html')

@app.route('/view-accounts')
def view_accounts():
    """Admin route to view all accounts (for demo purposes)"""
    users = User.query.all()
    accounts = []
    for user in users:
        accounts.append({
            'email': user.email,
            'password': user.password,
            'created_at': user.created_at,
            'last_login': user.last_login
        })
    return jsonify({'accounts': accounts})

@app.route('/login-guest')
def login_guest():
    if get_current_user():
        return redirect(url_for('home'))
    
    try:
        guest_email = "guest@wildlife.com"
        guest_user = User.query.filter_by(email=guest_email).first()
        
        if not guest_user:
            guest_user = User(email=guest_email, password="guest123", verified=True)
            db.session.add(guest_user)
            db.session.commit()
        
        session['user_id'] = guest_user.id
        session['user_email'] = guest_user.email
        session.permanent = True
        
        flash('Logged in as guest!', 'success')
        return redirect(url_for('home'))
        
    except Exception as e:
        flash('Guest login failed. Please try regular registration.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# Database Management Routes
@app.route('/admin/backup')
def admin_backup():
    """Manual backup trigger"""
    if create_backup():
        flash('Backup created successfully!', 'success')
    else:
        flash('Backup failed!', 'error')
    return redirect(url_for('home'))

@app.route('/admin/restore')
def admin_restore():
    """Manual restore trigger"""
    if restore_from_backup():
        flash('Data restored successfully!', 'success')
    else:
        flash('Restore failed!', 'error')
    return redirect(url_for('home'))

@app.route('/admin/stats')
def admin_stats():
    """Admin statistics"""
    stats = {
        'total_users': User.query.count(),
        'total_incidents': Incident.query.count(),
        'latest_backup': DataBackup.query.order_by(DataBackup.created_at.desc()).first().created_at.isoformat() if DataBackup.query.first() else 'No backups',
        'session_lifetime_days': 30
    }
    return jsonify(stats)

# ... (Keep all your existing API routes for incidents, predictions, hotspots, etc.)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {str(error)}")
    return render_template('500.html'), 500

# Health check with database verification
@app.route('/health')
def health_check():
    try:
        user_count = User.query.count()
        incident_count = Incident.query.count()
        return jsonify({
            'status': 'healthy', 
            'timestamp': datetime.utcnow().isoformat(),
            'users': user_count,
            'incidents': incident_count,
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# Initialize database
print("Starting Wildlife Incident Reporter with Persistent Sessions...")
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)