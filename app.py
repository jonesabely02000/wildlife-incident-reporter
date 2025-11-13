from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import csv
from datetime import datetime
from io import BytesIO, StringIO
import json

app = Flask(__name__)

# Database configuration - Use SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///incidents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create upload directories
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('static/exports', exist_ok=True)

db = SQLAlchemy(app)

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

# API Routes - MUST BE AFTER app AND db DEFINITION
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
            db.session.flush()  # Get ID without committing
            synced_ids.append({'local_id': incident_data.get('local_id'), 'server_id': incident.id})
        
        db.session.commit()
        return jsonify({'success': True, 'synced': synced_ids})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Original Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/report', methods=['GET', 'POST'])
def report_incident():
    if request.method == 'POST':
        try:
            # Get current timestamp for start/end times
            current_time = datetime.now().strftime('%Y-%m-%dT%H:%M')
            
            incident = Incident(
                # CRRT Member Details
                start_time=request.form.get('start_time') or current_time,
                end_time=request.form.get('end_time') or current_time,
                crrt_member_name=request.form.get('crrt_member_name', 'Unknown'),
                
                # Incident Details
                incident_date=request.form.get('incident_date', ''),
                incident_time=request.form.get('incident_time', ''),
                
                # GPS Location
                latitude=request.form.get('latitude', type=float) or 0.0,
                longitude=request.form.get('longitude', type=float) or 0.0,
                altitude=request.form.get('altitude', type=float) or 0.0,
                precision=request.form.get('precision', type=float) or 0.0,
                gps_location=f"{request.form.get('latitude', 0)} {request.form.get('longitude', 0)} {request.form.get('altitude', 0)} {request.form.get('precision', 0)}",
                
                # Incident Information
                incident_type=request.form.get('incident_type', 'Unknown'),
                elephants_observed=request.form.get('elephants_observed', type=int) or 0,
                
                # Response Methods
                response_noise='response_noise' in request.form,
                response_fire='response_fire' in request.form,
                response_chili='response_chili' in request.form,
                response_flashlight='response_flashlight' in request.form,
                response_other='response_other' in request.form,
                response_other_text=request.form.get('response_other_text', ''),
                
                # Response Outcome
                response_outcome=request.form.get('response_outcome', 'Unknown'),
                injuries_or_deaths=request.form.get('injuries_or_deaths', 'No one injured'),
                estimated_loss=request.form.get('estimated_loss', type=float) or 0.0,
                
                # Additional Information
                additional_comments=request.form.get('additional_comments', '')
            )
            
            db.session.add(incident)
            db.session.commit()
            return redirect(url_for('get_incidents'))
            
        except Exception as e:
            db.session.rollback()
            return f"Error submitting form: {str(e)}", 500

    return render_template('report.html')

@app.route('/incidents')
def get_incidents():
    try:
        incidents = Incident.query.all()
        return render_template('incidents.html', incidents=incidents)
    except Exception as e:
        return f"Error loading incidents: {str(e)}", 500

@app.route('/export')
def export_incidents():
    try:
        incidents = Incident.query.all()
        
        # Create CSV in memory - FIXED: Use BytesIO for binary mode
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
        
        # Convert to BytesIO for binary transmission - FIXED
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
        return f"Error exporting data: {str(e)}", 500

# Initialize database
with app.app_context():
    db.create_all()
    print("Database initialized successfully")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)