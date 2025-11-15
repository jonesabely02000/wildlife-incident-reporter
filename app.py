import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import logging
import csv
from io import StringIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Handle Heroku-style database URLs
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    verified = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    description = db.Column(db.Text)  # Added description field
    reported_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper function to get current user
def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

# Login required decorator
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

# Initialize database
def init_db():
    with app.app_context():
        try:
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully")
            
            # Create guest user if doesn't exist
            guest_email = "guest@wildlife.com"
            if not User.query.filter_by(email=guest_email).first():
                print("Creating guest user...")
                guest_user = User(email=guest_email, password="guest123", verified=True)
                db.session.add(guest_user)
                db.session.commit()
                print("Guest user created successfully")
            else:
                print("Guest user already exists")
                
        except Exception as e:
            print(f"Database initialization error: {str(e)}")

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
        incidents = Incident.query.filter_by(reported_by=user.email).order_by(Incident.date.desc()).all()
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

# API Routes
@app.route('/api/incidents', methods=['GET'])
@login_required
def get_incidents():
    try:
        user = get_current_user()
        incidents = Incident.query.filter_by(reported_by=user.email).all()
        
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
                'reported_by': incident.reported_by,
                'created_at': incident.created_at.isoformat()
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
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['date', 'latitude', 'longitude', 'species', 'incident_type', 'severity']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        incident = Incident(
            date=datetime.fromisoformat(data['date'].replace('Z', '+00:00')),
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
        
        return jsonify({
            'message': 'Incident reported successfully',
            'incident_id': incident.id
        }), 201
        
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
        
        if file and file.filename.endswith('.csv'):
            # Read CSV file
            stream = StringIO(file.stream.read().decode('UTF-8'))
            csv_reader = csv.DictReader(stream)
            imported_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, 2):  # Start from 2 (header is row 1)
                try:
                    # Handle different column name formats
                    date_str = row.get('Date') or row.get('date') or row.get('Incident Date')
                    latitude = row.get('Latitude') or row.get('latitude')
                    longitude = row.get('Longitude') or row.get('longitude')
                    species = row.get('Species') or row.get('species')
                    incident_type = row.get('IncidentType') or row.get('Incident Type') or row.get('incident_type')
                    severity = row.get('Severity') or row.get('severity')
                    description = row.get('Description') or row.get('description') or ''
                    
                    # Validate required fields
                    if not all([date_str, latitude, longitude, species, incident_type, severity]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue
                    
                    # Parse date (handle different formats)
                    try:
                        incident_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except ValueError:
                        try:
                            incident_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                incident_date = datetime.strptime(date_str, '%Y-%m-%d')
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid date format - {date_str}")
                                continue
                    
                    incident = Incident(
                        date=incident_date,
                        latitude=float(latitude),
                        longitude=float(longitude),
                        species=species,
                        incident_type=incident_type,
                        severity=severity,
                        description=description,
                        reported_by=user.email
                    )
                    
                    db.session.add(incident)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
            
            db.session.commit()
            
            result = {
                'message': f'Imported {imported_count} incidents successfully',
                'imported': imported_count,
                'errors': errors
            }
            
            if errors:
                result['warning'] = f'Completed with {len(errors)} errors'
            
            return jsonify(result)
        else:
            return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error importing incidents: {str(e)}")
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@app.route('/api/generate-predictions', methods=['GET'])
@login_required
def generate_predictions():
    user = get_current_user()
    
    try:
        incidents = Incident.query.filter_by(reported_by=user.email).all()
        
        if len(incidents) < 2:
            return jsonify({'error': 'Need at least 2 incidents to generate predictions'}), 400
        
        predictions = []
        for i, incident in enumerate(incidents[:5]):
            risk_level = "HIGH" if incident.severity == "High" else "MEDIUM"
            predictions.append({
                'area_name': f'Area {i+1}',
                'latitude': incident.latitude,
                'longitude': incident.longitude,
                'risk_level': risk_level,
                'reason': f'Based on {incident.species} {incident.incident_type} incident'
            })
        
        return jsonify({'predictions': predictions})
    except Exception as e:
        logger.error(f"Error generating predictions: {str(e)}")
        return jsonify({'error': 'Failed to generate predictions'}), 500

@app.route('/api/generate-hotspots', methods=['GET'])
@login_required
def generate_hotspots():
    user = get_current_user()
    
    try:
        incidents = Incident.query.filter_by(reported_by=user.email).all()
        
        if len(incidents) < 2:
            return jsonify({'error': 'Need at least 2 incidents to identify hotspots'}), 400
        
        hotspots = []
        species_count = {}
        
        for incident in incidents:
            species_count[incident.species] = species_count.get(incident.species, 0) + 1
        
        main_species = sorted(species_count.items(), key=lambda x: x[1], reverse=True)[:3]
        main_species_names = [species for species, count in main_species]
        
        for i, incident in enumerate(incidents[:5]):
            hotspots.append({
                'name': f'Hotspot {i+1}',
                'center_lat': incident.latitude,
                'center_lng': incident.longitude,
                'incident_count': 1,
                'main_species': main_species_names
            })
        
        return jsonify({'hotspots': hotspots})
    except Exception as e:
        logger.error(f"Error generating hotspots: {str(e)}")
        return jsonify({'error': 'Failed to generate hotspots'}), 500

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    user = get_current_user()
    
    try:
        total_incidents = Incident.query.filter_by(reported_by=user.email).count()
        high_severity = Incident.query.filter_by(reported_by=user.email, severity='High').count()
        
        return jsonify({
            'total_incidents': total_incidents,
            'imported_incidents': total_incidents,
            'high_risk_areas': min(5, total_incidents),
            'high_severity_count': high_severity,
            'data_coverage': min(100, total_incidents * 10)
        })
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        return jsonify({'error': 'Failed to load statistics'}), 500

# Export route
@app.route('/export')
@login_required
def export_incidents():
    user = get_current_user()
    
    try:
        incidents = Incident.query.filter_by(reported_by=user.email).all()
        
        output = []
        output.append('ID,Date,Latitude,Longitude,Species,IncidentType,Severity,Description,ReportedBy,CreatedAt')
        
        for incident in incidents:
            output.append(f'{incident.id},{incident.date},{incident.latitude},{incident.longitude},{incident.species},{incident.incident_type},{incident.severity},"{incident.description}",{incident.reported_by},{incident.created_at}')
        
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

# Initialize database when app starts
print("Starting Wildlife Incident Reporter...")
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)