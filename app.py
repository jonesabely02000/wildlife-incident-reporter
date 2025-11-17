import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import logging
import csv
from io import StringIO
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123-change-in-production')

# Handle database URL for different environments
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///wildlife.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

db = SQLAlchemy(app)

# Database Models
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
    description = db.Column(db.Text)
    reported_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper Functions
def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
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
            
            # Create guest user
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
        # Show user's own incidents only
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

# ... (login, register, logout routes remain the same - keep your existing code)

# API Routes - UPDATED FOR TEAM COLLABORATION
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

@app.route('/api/all-incidents', methods=['GET'])
@login_required
def get_all_incidents_api():
    """Get ALL incidents for team predictions and hotspots"""
    try:
        incidents = get_all_incidents()
        
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
        
        return jsonify({'incidents': incidents_data, 'total': len(incidents_data)})
    except Exception as e:
        logger.error(f"Error in get_all_incidents: {str(e)}")
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
        
        # Parse date
        try:
            incident_date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
        
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
        
        return jsonify({
            'message': 'Incident reported successfully',
            'incident_id': incident.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reporting incident: {str(e)}")
        return jsonify({'error': f'Failed to report incident: {str(e)}'}), 500

@app.route('/api/generate-predictions', methods=['GET'])
@login_required
def generate_predictions():
    try:
        # Use ALL incidents for predictions (team collaboration)
        incidents = get_all_incidents()
        
        if len(incidents) < 2:
            return jsonify({'error': 'Need at least 2 incidents to generate predictions. Currently team has ' + str(len(incidents)) + ' incidents.'}), 400
        
        # Advanced prediction logic using all team data
        predictions = generate_advanced_predictions(incidents)
        
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
        
        # Advanced hotspot detection using all team data
        hotspots = generate_advanced_hotspots(incidents)
        
        return jsonify({
            'hotspots': hotspots,
            'total_incidents_used': len(incidents),
            'data_source': 'team_collaboration'
        })
    except Exception as e:
        logger.error(f"Error generating hotspots: {str(e)}")
        return jsonify({'error': 'Failed to generate hotspots'}), 500

def generate_advanced_predictions(incidents):
    """Generate predictions using all team incidents"""
    predictions = []
    
    # Group incidents by area clusters
    clusters = cluster_incidents(incidents)
    
    for i, cluster in enumerate(clusters[:6]):  # Top 6 clusters
        if not cluster:
            continue
            
        # Calculate cluster center
        center_lat = sum(inc.latitude for inc in cluster) / len(cluster)
        center_lng = sum(inc.longitude for inc in cluster) / len(cluster)
        
        # Calculate risk level based on severity and frequency
        high_severity_count = sum(1 for inc in cluster if inc.severity == 'High')
        medium_severity_count = sum(1 for inc in cluster if inc.severity == 'Medium')
        
        if high_severity_count > 0:
            risk_level = "VERY HIGH"
        elif medium_severity_count > 0:
            risk_level = "HIGH"
        else:
            risk_level = "MEDIUM"
        
        # Get most common species in this cluster
        species_counter = Counter(inc.species for inc in cluster)
        main_species = species_counter.most_common(2)
        
        predictions.append({
            'area_name': f'Risk Zone {i+1}',
            'latitude': round(center_lat, 6),
            'longitude': round(center_lng, 6),
            'risk_level': risk_level,
            'incident_count': len(cluster),
            'main_species': [species for species, count in main_species],
            'reason': f'Based on {len(cluster)} incidents including {high_severity_count} high severity'
        })
    
    return predictions

def generate_advanced_hotspots(incidents):
    """Generate hotspots using all team incidents"""
    hotspots = []
    
    # Group incidents by area clusters
    clusters = cluster_incidents(incidents)
    
    for i, cluster in enumerate(clusters[:8]):  # Top 8 hotspots
        if not cluster:
            continue
            
        # Calculate cluster center
        center_lat = sum(inc.latitude for inc in cluster) / len(cluster)
        center_lng = sum(inc.longitude for inc in cluster) / len(cluster)
        
        # Get species distribution
        species_counter = Counter(inc.species for inc in cluster)
        main_species = [species for species, count in species_counter.most_common(3)]
        
        # Get incident type distribution
        type_counter = Counter(inc.incident_type for inc in cluster)
        main_types = [inc_type for inc_type, count in type_counter.most_common(2)]
        
        hotspots.append({
            'name': f'Hotspot {i+1}',
            'center_lat': round(center_lat, 6),
            'center_lng': round(center_lng, 6),
            'incident_count': len(cluster),
            'main_species': main_species,
            'main_incident_types': main_types,
            'radius_km': min(5, max(1, len(cluster) // 2))  # Dynamic radius based on incident count
        })
    
    return hotspots

def cluster_incidents(incidents, max_distance_km=10):
    """Group incidents into geographic clusters"""
    if not incidents:
        return []
    
    clusters = []
    used_incidents = set()
    
    for incident in incidents:
        if incident.id in used_incidents:
            continue
            
        cluster = [incident]
        used_incidents.add(incident.id)
        
        # Find nearby incidents
        for other_incident in incidents:
            if (other_incident.id not in used_incidents and 
                calculate_distance(incident.latitude, incident.longitude, 
                                 other_incident.latitude, other_incident.longitude) <= max_distance_km):
                cluster.append(other_incident)
                used_incidents.add(other_incident.id)
        
        clusters.append(cluster)
    
    # Sort clusters by size (largest first)
    clusters.sort(key=len, reverse=True)
    return clusters

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

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

# ... (rest of your existing routes - export, debug, etc.)

# Initialize database
print("Starting Wildlife Incident Reporter with Team Collaboration...")
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)