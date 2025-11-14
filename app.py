from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import os
import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import json
import secrets

# Get the directory of the current script
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
    static_folder=os.path.join(base_dir, 'static'),
    template_folder=os.path.join(base_dir, 'templates')
)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///incidents.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration (for verification)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # CRRT Member Details - ALL REQUIRED FIELDS
    start_time = db.Column(db.String(50), nullable=False, default=datetime.now().strftime('%Y-%m-%d %H:%M'))
    end_time = db.Column(db.String(50), nullable=False, default=datetime.now().strftime('%Y-%m-%d %H:%M'))
    crrt_member_name = db.Column(db.String(100), nullable=False)
    
    # Incident Details
    incident_date = db.Column(db.String(50), nullable=False)
    incident_time = db.Column(db.String(50), nullable=False)
    
    # GPS Location
    gps_location = db.Column(db.String(200), nullable=False, default="0 0 0 0")
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    altitude = db.Column(db.Float, default=0)
    precision = db.Column(db.Float, default=0)
    
    # Incident Information
    incident_type = db.Column(db.String(100), nullable=False)
    elephants_observed = db.Column(db.Integer, nullable=False)
    
    # Response Methods
    response_noise = db.Column(db.Boolean, default=False)
    response_fire = db.Column(db.Boolean, default=False)
    response_chili = db.Column(db.Boolean, default=False)
    response_flashlight = db.Column(db.Boolean, default=False)
    response_other = db.Column(db.Boolean, default=False)
    response_other_text = db.Column(db.String(200), default="")
    
    # Response Outcome
    response_outcome = db.Column(db.String(200), nullable=False)
    injuries_or_deaths = db.Column(db.String(100), nullable=False)
    estimated_loss = db.Column(db.Float, nullable=False)
    
    # Additional Information
    additional_comments = db.Column(db.Text, default="")
    
    # User association
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.password == password:  # In production, use proper password hashing!
            if user.verified:
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Please verify your email address first.', 'warning')
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html')
        
        # Generate verification token
        token = secrets.token_urlsafe(32)
        
        user = User(email=email, password=password, verification_token=token)  # Hash passwords in production!
        db.session.add(user)
        db.session.commit()
        
        # Send verification email (optional - can be skipped for demo)
        try:
            send_verification_email(user)
            flash('Registration successful! Please check your email for verification.', 'success')
        except:
            flash('Registration successful! But email verification failed.', 'warning')
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if user:
        user.verified = True
        user.verification_token = None
        db.session.commit()
        flash('Email verified successfully! You can now log in.', 'success')
    else:
        flash('Invalid verification token.', 'error')
    return redirect(url_for('login'))

@app.route('/guest')
def guest_access():
    # Create a temporary guest user or use session-based guest access
    flash('You are browsing as a guest. Some features are limited.', 'info')
    return redirect(url_for('home'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

def send_verification_email(user):
    """Send verification email (optional for demo)"""
    try:
        token = serializer.dumps(user.email, salt='email-verification')
        verify_url = url_for('verify_email', token=token, _external=True)
        
        msg = Message('Verify Your Email - Wildlife Incident Reporter',
                      recipients=[user.email])
        msg.body = f'''Please verify your email by clicking the link below:
{verify_url}

If you didn't create an account, please ignore this email.
'''
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# Prediction/Forecasting Routes
@app.route('/predictions')
def predictions():
    """Show hotspot predictions and forecasting"""
    try:
        incidents = Incident.query.all()
        
        if len(incidents) < 3:
            return render_template('predictions.html', 
                                 hotspots=[], 
                                 day_patterns=[],
                                 message="Need more data for predictions (minimum 3 incidents)")
        
        # Simple hotspot detection without heavy dependencies
        hotspots = simple_hotspot_detection(incidents)
        
        # Day of week patterns
        day_patterns = analyze_day_patterns_simple(incidents)
        
        return render_template('predictions.html', 
                             hotspots=hotspots, 
                             day_patterns=day_patterns,
                             total_incidents=len(incidents))
        
    except Exception as e:
        return render_template('predictions.html', 
                             hotspots=[], 
                             day_patterns=[],
                             message=f"Error generating predictions: {str(e)}")

def simple_hotspot_detection(incidents):
    """Simple hotspot detection without scikit-learn"""
    try:
        if len(incidents) < 2:
            return []
            
        # Group nearby incidents manually
        hotspots = []
        processed = set()
        
        for i, incident in enumerate(incidents):
            if i in processed:
                continue
                
            # Find incidents within 0.01 degrees (~1km)
            nearby = []
            for j, other in enumerate(incidents):
                if (abs(incident.latitude - other.latitude) < 0.01 and 
                    abs(incident.longitude - other.longitude) < 0.01):
                    nearby.append(other)
                    processed.add(j)
            
            if len(nearby) >= 2:  # At least 2 incidents to be a hotspot
                avg_lat = sum(inc.latitude for inc in nearby) / len(nearby)
                avg_lng = sum(inc.longitude for inc in nearby) / len(nearby)
                
                hotspots.append({
                    'center_lat': avg_lat,
                    'center_lng': avg_lng,
                    'incident_count': len(nearby),
                    'radius': 0.005  # Fixed radius for simplicity
                })
        
        return sorted(hotspots, key=lambda x: x['incident_count'], reverse=True)[:5]
        
    except Exception as e:
        print(f"Hotspot detection error: {e}")
        return []

def analyze_day_patterns_simple(incidents):
    """Analyze incident patterns by day of week without pandas"""
    try:
        day_counts = {}
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for incident in incidents:
            try:
                # Parse date manually
                date_parts = incident.incident_date.split('-')
                if len(date_parts) == 3:
                    year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                    date_obj = datetime(year, month, day)
                    day_name = day_names[date_obj.weekday()]
                    day_counts[day_name] = day_counts.get(day_name, 0) + 1
            except:
                continue
        
        day_patterns = []
        total_incidents = len(incidents)
        
        for day in day_names:
            count = day_counts.get(day, 0)
            percentage = (count / total_incidents) * 100 if total_incidents > 0 else 0
            
            # Risk level based on percentage
            if percentage > 20:
                risk = 'High'
            elif percentage > 10:
                risk = 'Medium'
            else:
                risk = 'Low'
                
            day_patterns.append({
                'day': day,
                'count': count,
                'percentage': round(percentage, 1),
                'risk': risk
            })
        
        return day_patterns
        
    except Exception as e:
        print(f"Day pattern analysis error: {e}")
        return []

# Update existing routes with authentication
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/report', methods=['GET', 'POST'])
def report_incident():
    if request.method == 'POST':
        try:
            current_time = datetime.now().strftime('%Y-%m-%dT%H:%M')
            
            incident = Incident(
                start_time=request.form.get('start_time') or current_time,
                end_time=request.form.get('end_time') or current_time,
                crrt_member_name=request.form.get('crrt_member_name', 'Unknown'),
                incident_date=request.form.get('incident_date', ''),
                incident_time=request.form.get('incident_time', ''),
                latitude=request.form.get('latitude', type=float) or 0.0,
                longitude=request.form.get('longitude', type=float) or 0.0,
                altitude=request.form.get('altitude', type=float) or 0.0,
                precision=request.form.get('precision', type=float) or 0.0,
                gps_location=f"{request.form.get('latitude', 0)} {request.form.get('longitude', 0)} {request.form.get('altitude', 0)} {request.form.get('precision', 0)}",
                incident_type=request.form.get('incident_type', 'Unknown'),
                elephants_observed=request.form.get('elephants_observed', type=int) or 0,
                response_noise='response_noise' in request.form,
                response_fire='response_fire' in request.form,
                response_chili='response_chili' in request.form,
                response_flashlight='response_flashlight' in request.form,
                response_other='response_other' in request.form,
                response_other_text=request.form.get('response_other_text', ''),
                response_outcome=request.form.get('response_outcome', 'Unknown'),
                injuries_or_deaths=request.form.get('injuries_or_deaths', 'No one injured'),
                estimated_loss=request.form.get('estimated_loss', type=float) or 0.0,
                additional_comments=request.form.get('additional_comments', ''),
                user_id=current_user.id if current_user.is_authenticated else None
            )
            
            db.session.add(incident)
            db.session.commit()
            flash('Incident reported successfully!', 'success')
            return redirect(url_for('get_incidents'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting form: {str(e)}', 'error')
    
    return render_template('report.html')

@app.route('/incidents')
def get_incidents():
    try:
        if current_user.is_authenticated and current_user.verified:
            incidents = Incident.query.all()
        else:
            incidents = Incident.query.limit(50).all()  # Limit for guests
            
        return render_template('incidents.html', incidents=incidents)
    except Exception as e:
        flash(f'Error loading incidents: {str(e)}', 'error')
        return render_template('incidents.html', incidents=[])

@app.route('/export')
@login_required
def export_incidents():
    if not current_user.verified:
        flash('Please verify your email to export data.', 'error')
        return redirect(url_for('get_incidents'))
        
    try:
        incidents = Incident.query.all()
        
        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Start time', 'End time', 'Name of CRRT member', 'Date of incident', 'Time of incident',
            'GPS location', 'Latitude', 'Longitude', 'Altitude', 'Precision',
            'Type of incident', 'Number of elephants observed', 'Response outcome',
            'Was anyone injured or killed?', 'Estimated loss (Tsh or in-kind)', 'Additional comments'
        ])
        
        # Write data
        for incident in incidents:
            writer.writerow([
                incident.start_time,
                incident.end_time,
                incident.crrt_member_name,
                incident.incident_date,
                incident.incident_time,
                incident.gps_location,
                incident.latitude,
                incident.longitude,
                incident.altitude,
                incident.precision,
                incident.incident_type,
                incident.elephants_observed,
                incident.response_outcome,
                incident.injuries_or_deaths,
                incident.estimated_loss,
                incident.additional_comments
            ])
        
        # Convert to BytesIO for binary transmission
        mem = BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()
        
        return send_file(
            mem,
            as_attachment=True,
            download_name='wildlife_incidents.csv',
            mimetype='text/csv'
        )
        
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'error')
        return redirect(url_for('get_incidents'))

# API Routes
@app.route('/api/incidents', methods=['GET', 'POST'])
def api_incidents():
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            incident = Incident(
                start_time=data.get('start_time', ''),
                end_time=data.get('end_time', ''),
                crrt_member_name=data.get('crrt_member_name', ''),
                incident_date=data.get('incident_date', ''),
                incident_time=data.get('incident_time', ''),
                latitude=data.get('latitude', 0),
                longitude=data.get('longitude', 0),
                altitude=data.get('altitude', 0),
                precision=data.get('precision', 0),
                gps_location=f"{data.get('latitude', 0)} {data.get('longitude', 0)} {data.get('altitude', 0)} {data.get('precision', 0)}",
                incident_type=data.get('incident_type', ''),
                elephants_observed=data.get('elephants_observed', 0),
                response_noise=data.get('response_noise', False),
                response_fire=data.get('response_fire', False),
                response_chili=data.get('response_chili', False),
                response_flashlight=data.get('response_flashlight', False),
                response_other=data.get('response_other', False),
                response_other_text=data.get('response_other_text', ''),
                response_outcome=data.get('response_outcome', ''),
                injuries_or_deaths=data.get('injuries_or_deaths', ''),
                estimated_loss=data.get('estimated_loss', 0),
                additional_comments=data.get('additional_comments', '')
            )
            
            db.session.add(incident)
            db.session.commit()
            return jsonify({'success': True, 'id': incident.id})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    else:  # GET request
        incidents = Incident.query.all()
        return jsonify([{
            'id': i.id,
            'crrt_member_name': i.crrt_member_name,
            'incident_date': i.incident_date,
            'incident_time': i.incident_time,
            'latitude': i.latitude,
            'longitude': i.longitude,
            'incident_type': i.incident_type,
            'elephants_observed': i.elephants_observed,
            'estimated_loss': i.estimated_loss
        } for i in incidents])

@app.route('/api/sync-pending', methods=['POST'])
def sync_pending():
    """Sync pending incidents from offline storage"""
    try:
        data = request.get_json()
        pending_incidents = data.get('incidents', [])
        
        synced_ids = []
        for incident_data in pending_incidents:
            incident = Incident(
                start_time=incident_data.get('start_time', ''),
                end_time=incident_data.get('end_time', ''),
                crrt_member_name=incident_data.get('crrt_member_name', ''),
                incident_date=incident_data.get('incident_date', ''),
                incident_time=incident_data.get('incident_time', ''),
                latitude=incident_data.get('latitude', 0),
                longitude=incident_data.get('longitude', 0),
                altitude=incident_data.get('altitude', 0),
                precision=incident_data.get('precision', 0),
                gps_location=f"{incident_data.get('latitude', 0)} {incident_data.get('longitude', 0)} {incident_data.get('altitude', 0)} {incident_data.get('precision', 0)}",
                incident_type=incident_data.get('incident_type', ''),
                elephants_observed=incident_data.get('elephants_observed', 0),
                response_noise=incident_data.get('response_noise', False),
                response_fire=incident_data.get('response_fire', False),
                response_chili=incident_data.get('response_chili', False),
                response_flashlight=incident_data.get('response_flashlight', False),
                response_other=incident_data.get('response_other', False),
                response_other_text=incident_data.get('response_other_text', ''),
                response_outcome=incident_data.get('response_outcome', ''),
                injuries_or_deaths=incident_data.get('injuries_or_deaths', ''),
                estimated_loss=incident_data.get('estimated_loss', 0),
                additional_comments=incident_data.get('additional_comments', '')
            )
            
            db.session.add(incident)
            db.session.flush()
            synced_ids.append({'local_id': incident_data.get('local_id'), 'server_id': incident.id})
        
        db.session.commit()
        return jsonify({'success': True, 'synced': synced_ids})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('home.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('home.html'), 500

# Initialize database
with app.app_context():
    db.create_all()
    print("Database initialized successfully")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)