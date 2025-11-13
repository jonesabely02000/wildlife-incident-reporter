from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import pandas as pd
from werkzeug.utils import secure_filename
import csv
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///incidents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['EXPORT_FOLDER'] = os.path.join('static', 'exports')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

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
    
    # Response Methods (Multiple selection)
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
    submission_time = db.Column(db.String(50), default=datetime.now().isoformat())

# Drop and recreate all tables
with app.app_context():
    db.drop_all()
    db.create_all()
    print("Database tables created successfully!")

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

        # Handle image upload
        image = request.files.get('picture')
        filename = None
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        incident = Incident(
            # CRRT Member Details
            start_time=start_time,
            end_time=end_time,
            crrt_member_name=crrt_member_name,
            
            # Incident Details
            incident_date=incident_date,
            incident_time=incident_time,
            
            # GPS Location
            gps_location=gps_location,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            precision=precision,
            
            # Incident Information
            incident_type=incident_type,
            elephants_observed=elephants_observed,
            
            # Response Methods
            response_noise=response_noise,
            response_fire=response_fire,
            response_chili=response_chili,
            response_flashlight=response_flashlight,
            response_other=response_other,
            response_other_text=response_other_text,
            
            # Response Outcome
            response_outcome=response_outcome,
            injuries_or_deaths=injuries_or_deaths,
            estimated_loss=estimated_loss,
            
            # Additional Information
            image_filename=filename,
            additional_comments=additional_comments,
            
            # Metadata
            submission_time=datetime.now().isoformat()
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
    data = []
    for i in incidents:
        # Build response methods string
        response_methods = []
        if i.response_noise: response_methods.append("Noise (shouting, banging)")
        if i.response_fire: response_methods.append("Fire or torch use")
        if i.response_chili: response_methods.append("Chili smoke or chili bombs")
        if i.response_flashlight: response_methods.append("Flashlight or spotlight")
        if i.response_other and i.response_other_text: response_methods.append(i.response_other_text)
        
        response_methods_str = " ".join(response_methods)
        
        data.append({
            'Start time': i.start_time,
            'End time': i.end_time,
            'Name of CRRT member': i.crrt_member_name,
            'Date of incident': i.incident_date,
            'Time of incident': i.incident_time,
            'GPS location': i.gps_location,
            '_GPS location_latitude': i.latitude,
            '_GPS location_longitude': i.longitude,
            '_GPS location_altitude': i.altitude,
            '_GPS location_precision': i.precision,
            'Type of incident': i.incident_type,
            'Number of elephants observed': i.elephants_observed,
            'Response method used': response_methods_str,
            'Response method used/Noise (shouting, banging)': 1 if i.response_noise else 0,
            'Response method used/Fire or torch use': 1 if i.response_fire else 0,
            'Response method used/Chili smoke or chili bombs': 1 if i.response_chili else 0,
            'Response method used/Flashlight or spotlight': 1 if i.response_flashlight else 0,
            'Response method used/Other': 1 if i.response_other else 0,
            'Response outcome': i.response_outcome,
            'Was anyone injured or killed?': i.injuries_or_deaths,
            'Estimated loss (Tsh or in-kind)': i.estimated_loss,
            'Upload photos (optional)': i.image_filename or '',
            'Upload photos (optional)_URL': f"/static/uploads/{i.image_filename}" if i.image_filename else '',
            'Additional comments': i.additional_comments or '',
            '_id': i.id,
            '_uuid': f"incident-{i.id}",
            '_submission_time': i.submission_time,
            '_validation_status': '',
            '_notes': '',
            '_status': 'submitted_via_web',
            '_submitted_by': '',
            '__version__': '1',
            '_tags': '',
            '_index': i.id
        })
    
    format_type = request.args.get('format', 'excel')
    
    if format_type == 'csv':
        # CSV Export
        csv_filepath = os.path.join(app.config['EXPORT_FOLDER'], 'wildlife_incidents.csv')
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if data:
                writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        return send_file(csv_filepath, as_attachment=True)
    else:
        # Excel Export
        try:
            df = pd.DataFrame(data)
            excel_filepath = os.path.join(app.config['EXPORT_FOLDER'], 'wildlife_incidents.xlsx')
            df.to_excel(excel_filepath, index=False)
            return send_file(excel_filepath, as_attachment=True)
        except ImportError:
            return redirect(url_for('export_incidents', format='csv'))

if __name__ == '__main__':
    app.run(debug=True)