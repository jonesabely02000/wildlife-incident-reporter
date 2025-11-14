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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wildlife.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    return User.query.get(int(user_id))

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
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        user = User(email=email, verified=True)  # Auto-verify for demo
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/verify-manual')
@login_required
def verify_manual():
    # Auto-verify for demo purposes
    current_user.verified = True
    db.session.commit()
    flash('Your account has been verified!', 'success')
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
        return jsonify({'error': str(e)}), 500

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
        return jsonify({'error': str(e)}), 500

@app.route('/api/report-incident', methods=['POST'])
@login_required
def report_incident_api():
    """API endpoint to report new incidents"""
    try:
        data = request.get_json()
        
        incident = Incident(
            date=datetime.strptime(data.get('date'), '%Y-%m-%d'),
            latitude=float(data.get('latitude')),
            longitude=float(data.get('longitude')),
            species=data.get('species'),
            incident_type=data.get('incident_type'),
            severity=data.get('severity'),
            distance_from_village_km=float(data.get('distance_from_village_km', 0)),
            reported_by=current_user.email
        )
        
        db.session.add(incident)
        db.session.commit()
        
        return jsonify({'message': 'Incident reported successfully', 'id': incident.id})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-incidents', methods=['POST'])
@login_required
def import_incidents():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # For Render.com deployment, we'll process CSV data directly
        if file.filename.lower().endswith('.csv'):
            imported_count = 0
            errors = []
            
            # Read CSV file
            stream = StringIO(file.stream.read().decode('UTF-8'), newline=None)
            csv_reader = csv.DictReader(stream)
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header
                try:
                    # Parse date
                    date_str = row.get('Date', '')
                    try:
                        incident_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        incident_date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    # Create incident
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
                    
                    # Validate coordinates
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
                'total_rows': row_num - 1,  # Subtract header
                'errors': errors[:10]
            })
            
        else:
            return jsonify({'error': 'Only CSV files are supported in this deployment'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@app.route('/api/generate-predictions', methods=['GET'])
@login_required
def generate_predictions():
    try:
        # Get all incidents for the current user
        incidents = Incident.query.filter_by(reported_by=current_user.email).all()
        
        if len(incidents) < 5:
            return jsonify({
                'error': 'Insufficient data for predictions. Need at least 5 incidents.'
            }), 400

        predictions = []
        
        # Simple clustering based on geographic proximity
        clusters = []
        for incident in incidents:
            added_to_cluster = False
            for cluster in clusters:
                # Check if incident is within 2km of cluster center
                cluster_center_lat = sum(inc.latitude for inc in cluster) / len(cluster)
                cluster_center_lng = sum(inc.longitude for inc in cluster) / len(cluster)
                
                distance = calculate_distance(
                    incident.latitude, incident.longitude,
                    cluster_center_lat, cluster_center_lng
                )
                
                if distance <= 2.0:  # 2km radius
                    cluster.append(incident)
                    added_to_cluster = True
                    break
            
            if not added_to_cluster:
                clusters.append([incident])
        
        # Generate predictions from clusters
        for i, cluster in enumerate(clusters):
            if len(cluster) >= 2:  # Only consider clusters with multiple incidents
                center_lat = sum(inc.latitude for inc in cluster) / len(cluster)
                center_lng = sum(inc.longitude for inc in cluster) / len(cluster)
                
                # Calculate risk level
                high_severity_count = sum(1 for inc in cluster if inc.severity == 'High')
                risk_score = len(cluster) + (high_severity_count * 2)
                
                if risk_score >= 5:
                    risk_level = "HIGH"
                elif risk_score >= 3:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"
                
                main_species = max(set(inc.species for inc in cluster), key=lambda x: list(inc.species for inc in cluster).count(x))
                
                predictions.append({
                    'area_name': f'Risk Zone {i+1}',
                    'latitude': center_lat,
                    'longitude': center_lng,
                    'risk_level': risk_level,
                    'risk_score': risk_score,
                    'incident_count': len(cluster),
                    'reason': f'Cluster of {len(cluster)} incidents with {high_severity_count} high severity. Main species: {main_species}'
                })
        
        # Add individual high severity incidents as predictions
        high_severity_incidents = [inc for inc in incidents if inc.severity == 'High']
        for i, incident in enumerate(high_severity_incidents[:3]):
            predictions.append({
                'area_name': f'High Risk Point {i+1}',
                'latitude': incident.latitude,
                'longitude': incident.longitude,
                'risk_level': 'HIGH',
                'risk_score': 3,
                'incident_count': 1,
                'reason': f'High severity incident involving {incident.species}'
            })
        
        return jsonify({
            'predictions': predictions[:10],  # Limit to 10 predictions
            'total_generated': len(predictions),
            'data_points_used': len(incidents)
        })

    except Exception as e:
        return jsonify({'error': f'Prediction generation failed: {str(e)}'}), 500

@app.route('/api/generate-hotspots', methods=['GET'])
@login_required
def generate_hotspots():
    try:
        incidents = Incident.query.filter_by(reported_by=current_user.email).all()
        
        if len(incidents) < 3:
            return jsonify({
                'error': 'Insufficient data for hotspot analysis. Need at least 3 incidents.'
            }), 400

        hotspots = []
        
        # Simple hotspot detection using grid-based approach
        grid_size = 0.02  # Approximately 2km grid
        
        # Create grid cells
        grid_cells = {}
        for incident in incidents:
            grid_x = round(incident.latitude / grid_size) * grid_size
            grid_y = round(incident.longitude / grid_size) * grid_size
            cell_key = (grid_x, grid_y)
            
            if cell_key not in grid_cells:
                grid_cells[cell_key] = []
            grid_cells[cell_key].append(incident)
        
        # Identify hotspots (cells with multiple incidents)
        for (cell_lat, cell_lng), cell_incidents in grid_cells.items():
            if len(cell_incidents) >= 2:  # Hotspot threshold
                species_counts = {}
                for inc in cell_incidents:
                    species_counts[inc.species] = species_counts.get(inc.species, 0) + 1
                
                main_species = sorted(species_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                main_species_names = [species for species, count in main_species]
                
                severity_counts = {
                    'High': len([inc for inc in cell_incidents if inc.severity == 'High']),
                    'Medium': len([inc for inc in cell_incidents if inc.severity == 'Moderate']),
                    'Low': len([inc for inc in cell_incidents if inc.severity == 'Low'])
                }
                
                hotspots.append({
                    'name': f'Hotspot {len(hotspots) + 1}',
                    'center_lat': cell_lat,
                    'center_lng': cell_lng,
                    'incident_count': len(cell_incidents),
                    'radius_km': 1.0,  # Fixed radius for grid-based approach
                    'main_species': main_species_names,
                    'severity_breakdown': severity_counts
                })
        
        hotspots.sort(key=lambda x: x['incident_count'], reverse=True)
        
        return jsonify({
            'hotspots': hotspots[:8],  # Limit to 8 hotspots
            'total_hotspots': len(hotspots),
            'total_incidents_analyzed': len(incidents)
        })
        
    except Exception as e:
        return jsonify({'error': f'Hotspot generation failed: {str(e)}'}), 500

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    try:
        total_incidents = Incident.query.filter_by(reported_by=current_user.email).count()
        imported_incidents = Incident.query.filter_by(reported_by=current_user.email, imported=True).count()
        
        # Calculate data coverage
        if total_incidents > 0:
            data_coverage = min(100, (total_incidents / 30) * 100)
        else:
            data_coverage = 0
            
        # Count high risk areas
        high_severity_count = Incident.query.filter_by(reported_by=current_user.email, severity='High').count()
        high_risk_areas = min(8, high_severity_count)
        
        return jsonify({
            'total_incidents': total_incidents,
            'imported_incidents': imported_incidents,
            'high_risk_areas': high_risk_areas,
            'data_coverage': round(data_coverage, 1)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper functions
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create demo user if not exists
        if not User.query.filter_by(email='jonesabely@gmail.com').first():
            demo_user = User(email='jonesabely@gmail.com', verified=True)
            demo_user.set_password('demo123')
            db.session.add(demo_user)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)