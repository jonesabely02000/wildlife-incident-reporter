import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import logging
import csv
from io import StringIO
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    verified = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)

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

# Helper Functions
def get_current_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
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

def get_all_incidents():
    """Get all incidents for team collaboration"""
    return Incident.query.order_by(Incident.date.desc()).all()

def get_user_incidents(user):
    """Get incidents for specific user"""
    return Incident.query.filter_by(reported_by=user.email).order_by(Incident.date.desc()).all()

def init_db():
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create guest user if doesn't exist
            guest_email = "guest@wildlife.com"
            if not User.query.filter_by(email=guest_email).first():
                guest_user = User(email=guest_email, password="guest123", verified=True)
                db.session.add(guest_user)
                db.session.commit()
                logger.info("Guest user created successfully")
                
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")

# Routes
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
            
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if get_current_user():
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        
        if user:
            flash(f'Password for {email}: {user.password}', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email not found', 'error')
    
    return render_template('forgot_password.html')

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

# Debug route
@app.route('/debug-session')
def debug_session():
    user = get_current_user()
    session_data = dict(session)
    
    safe_session = {k: v for k, v in session_data.items() if k not in ['_permanent']}
    
    debug_info = {
        'session_data': safe_session,
        'current_user': {
            'id': user.id if user else None,
            'email': user.email if user else None,
            'verified': user.verified if user else None
        },
        'is_authenticated': user is not None,
        'total_users': User.query.count(),
        'total_incidents': Incident.query.count() if user else 0
    }
    
    return jsonify(debug_info)

# API Routes
@app.route('/api/incidents', methods=['GET'])
@login_required
def get_incidents():
    try:
        user = get_current_user()
        incidents = get_user_incidents(user)
        
        incidents_data = []
        for incident in incidents:
            incidents_data.append({
                'id': incident.id,
                'date': incident.date.isoformat(),
                'latitude': incident.latitude,
                'longitude': incident.longitude,
                'species': incident.species,
                'incident_type': incident.incident_type,
                'severity': incident.severity,
                'description': incident.description,
                'reported_by': incident.reported_by
            })
        
        return jsonify({'incidents': incidents_data})
    except Exception as e:
        logger.error(f"Error in get_incidents: {str(e)}")
        return jsonify({'error': 'Failed to load incidents'}), 500

@app.route('/api/report-incident', methods=['POST'])
@login_required
def api_report_incident():
    user = get_current_user()
    
    try:
        # Get JSON data with proper error handling
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        logger.info(f"Received incident data: {data}")
        
        # Validate required fields
        required_fields = ['date', 'latitude', 'longitude', 'species', 'incident_type', 'severity']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Parse date with multiple format support
        date_str = data['date']
        try:
            if 'T' in date_str:
                incident_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                incident_date = datetime.fromisoformat(date_str)
        except ValueError:
            try:
                incident_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    incident_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS'}), 400
        
        # Create incident
        incident = Incident(
            date=incident_date,
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            species=data['species'],
            incident_type=data['incident_type'],
            severity=data['severity'],
            description=data.get('description', ''),
            reported_by=user.email
        )
        
        db.session.add(incident)
        db.session.commit()
        
        response_data = {
            'message': 'Incident reported successfully',
            'incident_id': incident.id
        }
        
        logger.info(f"Incident saved successfully: {incident.id}")
        return jsonify(response_data), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reporting incident: {str(e)}")
        return jsonify({'error': f'Failed to report incident: {str(e)}'}), 500

@app.route('/api/import-incidents', methods=['POST'])
@login_required
def import_incidents():
    user = get_current_user()
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400
        
        # Read and decode CSV file
        file_content = file.stream.read().decode('UTF-8')
        stream = StringIO(file_content)
        
        # Detect CSV dialect
        sample = file_content[:1024]
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        
        csv_reader = csv.DictReader(stream, dialect=dialect)
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, 2):
            try:
                # Flexible column name matching
                date_str = (row.get('Date') or row.get('date') or 
                           row.get('Incident Date') or row.get('incident_date'))
                latitude = (row.get('Latitude') or row.get('latitude') or 
                           row.get('Lat') or row.get('lat'))
                longitude = (row.get('Longitude') or row.get('longitude') or 
                            row.get('Lon') or row.get('lon') or row.get('Lng') or row.get('lng'))
                species = (row.get('Species') or row.get('species') or 
                          row.get('Animal') or row.get('animal'))
                incident_type = (row.get('IncidentType') or row.get('Incident Type') or 
                               row.get('incident_type') or row.get('Type') or row.get('type'))
                severity = (row.get('Severity') or row.get('severity') or 
                           row.get('Level') or row.get('level'))
                description = (row.get('Description') or row.get('description') or 
                              row.get('Comments') or row.get('comments') or '')
                
                # Validate required fields
                if not all([date_str, latitude, longitude, species, incident_type, severity]):
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                # Parse date
                incident_date = parse_date(date_str)
                if not incident_date:
                    errors.append(f"Row {row_num}: Invalid date format - {date_str}")
                    continue
                
                # Create incident
                incident = Incident(
                    date=incident_date,
                    latitude=float(latitude),
                    longitude=float(longitude),
                    species=species.strip(),
                    incident_type=incident_type.strip(),
                    severity=severity.strip(),
                    description=description.strip(),
                    reported_by=user.email
                )
                
                db.session.add(incident)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue
        
        db.session.commit()
        
        result = {
            'message': f'Successfully imported {imported_count} incidents',
            'imported': imported_count,
            'errors': errors
        }
        
        if errors:
            result['warning'] = f'Completed with {len(errors)} errors'
        
        return jsonify(result)
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing incidents: {str(e)}")
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

def parse_date(date_str):
    """Parse date from string with multiple format support"""
    date_str = str(date_str).strip()
    
    # Remove timezone info if present
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M',
        '%m/%d/%Y',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%d/%m/%Y'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None

@app.route('/api/generate-predictions', methods=['GET'])
@login_required
def generate_predictions():
    try:
        # Use ALL incidents for predictions (team collaboration)
        incidents = get_all_incidents()
        
        if len(incidents) < 2:
            return jsonify({'error': 'Need at least 2 incidents to generate predictions. Currently team has ' + str(len(incidents)) + ' incidents.'}), 400
        
        predictions = []
        for i, incident in enumerate(incidents[:6]):
            risk_level = "HIGH" if incident.severity == "High" else "MEDIUM"
            predictions.append({
                'area_name': f'Risk Zone {i+1}',
                'latitude': incident.latitude,
                'longitude': incident.longitude,
                'risk_level': risk_level,
                'reason': f'Based on {incident.species} {incident.incident_type} incident'
            })
        
        return jsonify({
            'predictions': predictions,
            'total_incidents_used': len(incidents),
            'data_source': 'team_collaboration'
        })
    except Exception as e:
        logger.error(f"Error generating predictions: {str(e)}")
        return jsonify({'error': 'Failed to generate predictions'}), 500

@app.route('/api/generate-hotspots', methods=['GET'])
@login_required
def generate_hotspots():
    try:
        # Use ALL incidents for hotspots (team collaboration)
        incidents = get_all_incidents()
        
        if len(incidents) < 2:
            return jsonify({'error': 'Need at least 2 incidents to identify hotspots. Currently team has ' + str(len(incidents)) + ' incidents.'}), 400
        
        hotspots = []
        species_count = {}
        
        for incident in incidents:
            species_count[incident.species] = species_count.get(incident.species, 0) + 1
        
        main_species = sorted(species_count.items(), key=lambda x: x[1], reverse=True)[:3]
        main_species_names = [species for species, count in main_species]
        
        for i, incident in enumerate(incidents[:8]):
            hotspots.append({
                'name': f'Hotspot {i+1}',
                'center_lat': incident.latitude,
                'center_lng': incident.longitude,
                'incident_count': 1,
                'main_species': main_species_names
            })
        
        return jsonify({
            'hotspots': hotspots,
            'total_incidents_used': len(incidents),
            'data_source': 'team_collaboration'
        })
    except Exception as e:
        logger.error(f"Error generating hotspots: {str(e)}")
        return jsonify({'error': 'Failed to generate hotspots'}), 500

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    user = get_current_user()
    
    try:
        # User's personal statistics
        user_incidents = get_user_incidents(user)
        user_total = len(user_incidents)
        user_high_severity = sum(1 for inc in user_incidents if inc.severity == 'High')
        
        # Team statistics
        team_incidents = get_all_incidents()
        team_total = len(team_incidents)
        team_high_severity = sum(1 for inc in team_incidents if inc.severity == 'High')
        
        return jsonify({
            # Personal stats
            'total_incidents': user_total,
            'high_severity_count': user_high_severity,
            'data_coverage': min(100, user_total * 10),
            
            # Team stats
            'team_total_incidents': team_total,
            'team_high_severity': team_high_severity,
            'team_members': User.query.count(),
            'team_data_coverage': min(100, team_total * 5)
        })
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        return jsonify({'error': 'Failed to load statistics'}), 500

@app.route('/export')
@login_required
def export_incidents():
    user = get_current_user()
    
    try:
        incidents = Incident.query.filter_by(reported_by=user.email).all()
        
        output = []
        output.append('ID,Date,Latitude,Longitude,Species,IncidentType,Severity,Description,ReportedBy')
        
        for incident in incidents:
            output.append(f'{incident.id},{incident.date},{incident.latitude},{incident.longitude},{incident.species},{incident.incident_type},{incident.severity},"{incident.description}",{incident.reported_by}')
        
        response = '\n'.join(output)
        return Response(
            response,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=incidents.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting incidents: {str(e)}")
        flash('Error exporting data', 'error')
        return redirect(url_for('view_incidents'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {str(error)}")
    return render_template('500.html'), 500

# Health check
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

# Initialize database
print("Starting Wildlife Incident Reporter with Team Collaboration...")
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)