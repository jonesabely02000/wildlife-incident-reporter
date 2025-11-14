from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-123-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    verified = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    species = db.Column(db.String(100), nullable=False)
    incident_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    reported_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper function to get current user
def get_current_user():
    if 'user_email' in session:
        return User.query.filter_by(email=session['user_email']).first()
    return None

# Login required decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
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
    user = get_current_user()
    return render_template('incidents.html', user=user)

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
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        print(f"Login attempt: {email}")
        
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_email'] = email
            session.permanent = True
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    # If user is already logged in, redirect to home
    if get_current_user():
        return redirect(url_for('home'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        print(f"Registration attempt: {email}")
        
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
            
            session['user_email'] = email
            session.permanent = True
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'error')
    
    # If user is already logged in, redirect to home
    if get_current_user():
        return redirect(url_for('home'))
    
    return render_template('register.html')

@app.route('/login-guest')
def login_guest():
    print("Guest login attempt")
    
    try:
        guest_email = "guest@wildlife.com"
        guest_user = User.query.filter_by(email=guest_email).first()
        
        if not guest_user:
            print("Creating new guest user")
            guest_user = User(email=guest_email, password="guest123", verified=True)
            db.session.add(guest_user)
            db.session.commit()
            print("Guest user created")
        else:
            print("Using existing guest user")
        
        session['user_email'] = guest_email
        session.permanent = True
        flash('Logged in as guest!', 'success')
        return redirect(url_for('home'))
        
    except Exception as e:
        print(f"Guest login error: {str(e)}")
        flash('Guest login failed. Please try regular registration.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# API Routes
@app.route('/api/import-incidents', methods=['POST'])
@login_required
def import_incidents():
    user = get_current_user()
    
    try:
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            import csv
            from io import StringIO
            
            stream = StringIO(file.stream.read().decode('UTF-8'))
            csv_reader = csv.DictReader(stream)
            imported_count = 0
            
            for row in csv_reader:
                try:
                    incident = Incident(
                        date=datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S'),
                        latitude=float(row['Latitude']),
                        longitude=float(row['Longitude']),
                        species=row['Species'],
                        incident_type=row['IncidentType'],
                        severity=row['Severity'],
                        reported_by=user.email
                    )
                    db.session.add(incident)
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing row: {e}")
                    continue
            
            db.session.commit()
            return jsonify({'message': f'Imported {imported_count} incidents', 'imported': imported_count})
        else:
            return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@app.route('/api/generate-predictions', methods=['GET'])
@login_required
def generate_predictions():
    user = get_current_user()
    
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

@app.route('/api/generate-hotspots', methods=['GET'])
@login_required
def generate_hotspots():
    user = get_current_user()
    
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

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    user = get_current_user()
    
    total_incidents = Incident.query.filter_by(reported_by=user.email).count()
    
    return jsonify({
        'total_incidents': total_incidents,
        'imported_incidents': total_incidents,
        'high_risk_areas': min(5, total_incidents),
        'data_coverage': min(100, total_incidents * 10)
    })

# Initialize database when app starts
print("Starting Wildlife Incident Reporter...")
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)