from flask import Flask, render_template, request, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import csv
from datetime import datetime
from io import StringIO

app = Flask(__name__)

# Database configuration
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///incidents.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['EXPORT_FOLDER'] = 'static/exports'

db = SQLAlchemy(app)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # CRRT Member Details
    start_time = db.Column(db.String(50), nullable=False)
    end_time = db.Column(db.String(50), nullable=False)
    crrt_member_name = db.Column(db.String(100), nullable=False)
    
    # Incident Details
    incident_date = db.Column(db.String(50), nullable=False)
    incident_time = db.Column(db.String(50), nullable=False)
    
    # GPS Location
    gps_location = db.Column(db.String(200), nullable=False)
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
    response_other_text = db.Column(db.String(200), nullable=True)
    
    # Response Outcome
    response_outcome = db.Column(db.String(200), nullable=False)
    injuries_or_deaths = db.Column(db.String(100), nullable=False)
    estimated_loss = db.Column(db.Float, nullable=False)
    
    # Media and Comments
    image_filename = db.Column(db.String(200), nullable=True)
    additional_comments = db.Column(db.Text, nullable=True)
    
    # Metadata
    submission_time = db.Column(db.String(50), default=lambda: datetime.now().isoformat())

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/report', methods=['GET', 'POST'])
def report_incident():
    if request.method == 'POST':
        # CRRT Member Details
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        crrt_member_name = request.form.get('crrt_member_name')
        
        # Incident Details
        incident_date = request.form.get('incident_date')
        incident_time = request.form.get('incident_time')
        
        # GPS Location
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        altitude = request.form.get('altitude', type=float, default=0)
        precision = request.form.get('precision', type=float, default=0)
        gps_location = f"{latitude} {longitude} {altitude} {precision}"
        
        # Incident Information
        incident_type = request.form.get('incident_type')
        elephants_observed = request.form.get('elephants_observed', type=int)
        
        # Response Methods
        response_noise = 'response_noise' in request.form
        response_fire = 'response_fire' in request.form
        response_chili = 'response_chili' in request.form
        response_flashlight = 'response_flashlight' in request.form
        response_other = 'response_other' in request.form
        response_other_text = request.form.get('response_other_text', '')
        
        # Response Outcome
        response_outcome = request.form.get('response_outcome')
        injuries_or_deaths = request.form.get('injuries_or_deaths')
        estimated_loss = request.form.get('estimated_loss', type=float)
        
        # Additional Information
        additional_comments = request.form.get('additional_comments', '')

        incident = Incident(
            start_time=start_time,
            end_time=end_time,
            crrt_member_name=crrt_member_name,
            incident_date=incident_date,
            incident_time=incident_time,
            gps_location=gps_location,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            precision=precision,
            incident_type=incident_type,
            elephants_observed=elephants_observed,
            response_noise=response_noise,
            response_fire=response_fire,
            response_chili=response_chili,
            response_flashlight=response_flashlight,
            response_other=response_other,
            response_other_text=response_other_text,
            response_outcome=response_outcome,
            injuries_or_deaths=injuries_or_deaths,
            estimated_loss=estimated_loss,
            additional_comments=additional_comments
        )
        
        db.session.add(incident)
        db.session.commit()
        return redirect(url_for('get_incidents'))

    return render_template('report.html')

@app.route('/incidents')
def get_incidents():
    incidents = Incident.query.all()
    return render_template('incidents.html', incidents=incidents)

@app.route('/export')
def export_incidents():
    incidents = Incident.query.all()
    
    # Create CSV data
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'CRRT Member', 'Incident Date', 'Incident Time', 
        'Latitude', 'Longitude', 'Incident Type', 'Elephants Observed',
        'Estimated Loss', 'Response Outcome', 'Injuries/Deaths'
    ])
    
    # Write data
    for incident in incidents:
        writer.writerow([
            incident.id,
            incident.crrt_member_name,
            incident.incident_date,
            incident.incident_time,
            incident.latitude,
            incident.longitude,
            incident.incident_type,
            incident.elephants_observed,
            incident.estimated_loss,
            incident.response_outcome,
            incident.injuries_or_deaths
        ])
    
    output.seek(0)
    
    return send_file(
        StringIO(output.getvalue()),
        as_attachment=True,
        download_name='wildlife_incidents.csv',
        mimetype='text/csv'
    )

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)