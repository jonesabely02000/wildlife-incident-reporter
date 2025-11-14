from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
import math
import csv
from io import StringIO
from sqlalchemy import func
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    species = db.Column(db.String(100), nullable=False)
    incident_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    distance_from_village_km = db.Column(db.Float, default=0)
    reported_by = db.Column(db.String(120), nullable=False)
    imported = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None

# Error handlers
@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', 
                         error="Internal Server Error", 
                         message="Something went wrong. Please try again later."), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', 
                         error="Page Not Found", 
                         message="The page you're looking for doesn't exist."), 404

# Routes
@app.route('/')
def index():
    return render_template('home.html', user=current_user)

@app.route('/home')
def home():
    return render_template('home.html', user=current_user)

@app.route('/view-incidents')
@login_required
def view_incidents():
    return render_template('incidents.html', user=current_user)

@app.route('/report-incident')
@login_required
def report_incident():
    return render_template('report.html', user=current_user)

@app.route('/predictions')
@login_required
def predictions():
    return render_template('predictions.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            
            if not email or not password:
                flash('Please fill in all fields', 'error')
                return render_template('login.html')
            
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('home'))
            else:
                flash('Invalid email or password', 'error')
        
        return render_template('login.html')
    except Exception as e:
        print(f"Login error: {str(e)}")
        flash('An error occurred during login. Please try again.', 'error')
        return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Validation
            if not email or not password or not confirm_password:
                flash('All fields are required', 'error')
                return render_template('register.html')
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long', 'error')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html')
            
            if not '@' in email or not '.' in email:
                flash('Please enter a valid email address', 'error')
                return render_template('register.html')
            
            # Check if user exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already registered. Please login instead.', 'error')
                return render_template('register.html')
            
            # Create new user
            user = User(email=email, verified=True)
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('login'))
            
        return render_template('register.html')
        
    except Exception as e:
        db.session.rollback()
        print(f"Registration error: {str(e)}")
        print(traceback.format_exc())
        flash('Registration failed. Please try again.', 'error')
        return render_template('register.html')

@app.route('/login-guest')
def login_guest():
    """Login as guest user"""
    try:
        # Use a simple guest account
        guest_email = "guest@wildlife.com"
        guest_password = "guest123"
        
        # Check if guest user exists
        guest_user = User.query.filter_by(email=guest_email).first()
        
        if not guest_user:
            # Create guest user
            guest_user = User(email=guest_email, verified=True)
            guest_user.set_password(guest_password)
            db.session.add(guest_user)
            db.session.commit()
            print("Guest user created successfully")
        else:
            print("Guest user already exists")
        
        # Login the guest user
        if guest_user and guest_user.check_password(guest_password):
            login_user(guest_user)
            flash('Logged in as guest user successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Guest login failed. Please try regular registration.', 'error')
            return redirect(url_for('login'))
            
    except Exception as e:
        db.session.rollback()
        print(f"Guest login error: {str(e)}")
        print(traceback.format_exc())
        flash('Guest login failed. Please try regular registration.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/verify-manual')
@login_required
def verify_manual():
    try:
        current_user.verified = True
        db.session.commit()
        flash('Your account has been verified!', 'success')
        return redirect(url_for('home'))
    except Exception as e:
        db.session.rollback()
        flash('Verification failed. Please try again.', 'error')
        return redirect(url_for('home'))

# API Routes
@app.route('/api/incidents')
@login_required
def get_incidents():
    """API endpoint to get incidents data"""
    try:
        incidents = Incident.query.filter_by(reported_by=current_user.email).all()
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
                'distance_from_village_km': incident.distance_from_village_km,
                'reported_by': incident.reported_by
            })
        
        return jsonify(incidents_data)
    
    except Exception as e:
        print(f"Get incidents error: {str(e)}")
        return jsonify({'error': 'Failed to fetch incidents'}), 500

@app.route('/api/export-incidents')
@login_required
def export_incidents():
    """Export incidents as CSV"""
    try:
        if not current_user.verified:
            return jsonify({'error': 'Email verification required for data export'}), 403
        
        incidents = Incident.query.filter_by(reported_by=current_user.email).all()
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Latitude', 'Longitude', 'Species', 'IncidentType', 'Severity', 'DistanceFromVillage_km'])
        
        for incident in incidents:
            writer.writerow([
                incident.date.strftime('%Y-%m-%d %H:%M:%S'),
                incident.latitude,
                incident.longitude,
                incident.species,
                incident.incident_type,
                incident.severity,
                incident.distance_from_village_km
            ])
        
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-disposition': 'attachment; filename=incidents_export.csv'}
        )
        
        return response
    
    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/import-incidents', methods=['POST'])
@login_required
def import_incidents():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if file.filename.lower().endswith('.csv'):
            imported_count = 0
            errors = []
            
            stream = StringIO(file.stream.read().decode('UTF-8'), newline=None)
            csv_reader = csv.DictReader(stream)
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    date_str = row.get('Date', '')
                    try:
                        incident_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        incident_date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    incident = Incident(
                        date=incident_date,
                        latitude=float(row.get('Latitude', 0)),
                        longitude=float(row.get('Longitude', 0)),
                        species=row.get('Species', 'Unknown'),
                        incident_type=row.get('IncidentType', 'Sighting'),
                        severity=row.get('Severity', 'Low'),
                        distance_from_village_km=float(row.get('DistanceFromVillage_km', 0)),
                        reported_by=current_user.email,
                        imported=True
                    )
                    
                    if not (-90 <= incident.latitude <= 90) or not (-180 <= incident.longitude <= 180):
                        errors.append(f"Row {row_num}: Invalid coordinates")
                        continue
                    
                    db.session.add(incident)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
            
            db.session.commit()
            
            return jsonify({
                'message': 'Import completed',
                'imported': imported_count,
                'total_rows': row_num - 1,
                'errors': errors[:10]
            })
            
        else:
            return jsonify({'error': 'Only CSV files are supported'}), 400

    except Exception as e:
        db.session.rollback()
        print(f"Import error: {str(e)}")
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@app.route('/api/generate-predictions', methods=['GET'])
@login_required
def generate_predictions():
    try:
        incidents = Incident.query.filter_by(reported_by=current_user.email).all()
        
        if len(incidents) < 3:
            return jsonify({
                'error': 'Insufficient data for predictions. Need at least 3 incidents.'
            }), 400

        predictions = []
        
        # Simple grid-based prediction
        grid_size = 0.02
        grid_cells = {}
        
        for incident in incidents:
            grid_x = round(incident.latitude / grid_size) * grid_size
            grid_y = round(incident.longitude / grid_size) * grid_size
            cell_key = (grid_x, grid_y)
            
            if cell_key not in grid_cells:
                grid_cells[cell_key] = []
            grid_cells[cell_key].append(incident)
        
        for (cell_lat, cell_lng), cell_incidents in grid_cells.items():
            if len(cell_incidents) >= 2:
                high_severity_count = sum(1 for inc in cell_incidents if inc.severity == 'High')
                risk_score = len(cell_incidents) + (high_severity_count * 2)
                
                if risk_score >= 3:
                    risk_level = "HIGH"
                elif risk_score >= 2:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"
                
                main_species = max(set(inc.species for inc in cell_incidents), 
                                 key=lambda x: list(inc.species for inc in cell_incidents).count(x))
                
                predictions.append({
                    'area_name': f'Risk Zone {len(predictions) + 1}',
                    'latitude': cell_lat,
                    'longitude': cell_lng,
                    'risk_level': risk_level,
                    'risk_score': risk_score,
                    'incident_count': len(cell_incidents),
                    'reason': f'Area with {len(cell_incidents)} incidents'
                })
        
        return jsonify({
            'predictions': predictions[:5],
            'total_generated': len(predictions),
            'data_points_used': len(incidents)
        })

    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return jsonify({'error': 'Prediction generation failed'}), 500

@app.route('/api/generate-hotspots', methods=['GET'])
@login_required
def generate_hotspots():
    try:
        incidents = Incident.query.filter_by(reported_by=current_user.email).all()
        
        if len(incidents) < 2:
            return jsonify({
                'error': 'Insufficient data for hotspot analysis. Need at least 2 incidents.'
            }), 400

        hotspots = []
        
        grid_size = 0.02
        grid_cells = {}
        
        for incident in incidents:
            grid_x = round(incident.latitude / grid_size) * grid_size
            grid_y = round(incident.longitude / grid_size) * grid_size
            cell_key = (grid_x, grid_y)
            
            if cell_key not in grid_cells:
                grid_cells[cell_key] = []
            grid_cells[cell_key].append(incident)
        
        for (cell_lat, cell_lng), cell_incidents in grid_cells.items():
            if len(cell_incidents) >= 2:
                species_counts = {}
                for inc in cell_incidents:
                    species_counts[inc.species] = species_counts.get(inc.species, 0) + 1
                
                main_species = sorted(species_counts.items(), key=lambda x: x[1], reverse=True)[:2]
                main_species_names = [species for species, count in main_species]
                
                hotspots.append({
                    'name': f'Hotspot {len(hotspots) + 1}',
                    'center_lat': cell_lat,
                    'center_lng': cell_lng,
                    'incident_count': len(cell_incidents),
                    'radius_km': 1.0,
                    'main_species': main_species_names
                })
        
        hotspots.sort(key=lambda x: x['incident_count'], reverse=True)
        
        return jsonify({
            'hotspots': hotspots[:5],
            'total_hotspots': len(hotspots),
            'total_incidents_analyzed': len(incidents)
        })
        
    except Exception as e:
        print(f"Hotspot error: {str(e)}")
        return jsonify({'error': 'Hotspot generation failed'}), 500

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    try:
        total_incidents = Incident.query.filter_by(reported_by=current_user.email).count()
        imported_incidents = Incident.query.filter_by(reported_by=current_user.email, imported=True).count()
        
        data_coverage = min(100, (total_incidents / 20) * 100) if total_incidents > 0 else 0
        high_risk_areas = min(5, total_incidents // 2)
        
        return jsonify({
            'total_incidents': total_incidents,
            'imported_incidents': imported_incidents,
            'high_risk_areas': high_risk_areas,
            'data_coverage': round(data_coverage, 1)
        })
        
    except Exception as e:
        print(f"Statistics error: {str(e)}")
        return jsonify({'error': 'Failed to get statistics'}), 500

# Helper functions
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Initialize database safely
def init_db():
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created/verified")
            
            # Create guest user if doesn't exist
            guest_email = "guest@wildlife.com"
            if not User.query.filter_by(email=guest_email).first():
                guest_user = User(email=guest_email, verified=True)
                guest_user.set_password("guest123")
                db.session.add(guest_user)
                db.session.commit()
                print("Guest user created")
            
        except Exception as e:
            print(f"Database init error: {str(e)}")
            print(traceback.format_exc())

# Create error page template
@app.route('/error-test')
def error_test():
    """Route to test error handling"""
    return render_template('error.html', 
                         error="Test Error", 
                         message="This is a test error page.")

if __name__ == '__main__':
    print("Starting Wildlife Incident Reporter...")
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)