from flask import Flask, render_template, request, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import csv
from datetime import datetime
from io import StringIO

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
    crrt_member_name = db.Column(db.String(100), nullable=False)
    incident_date = db.Column(db.String(50), nullable=False)
    incident_time = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    incident_type = db.Column(db.String(100), nullable=False)
    elephants_observed = db.Column(db.Integer, nullable=False)
    estimated_loss = db.Column(db.Float, nullable=False)
    response_outcome = db.Column(db.String(200), default="Unknown")
    injuries_or_deaths = db.Column(db.String(100), default="No one injured")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/report', methods=['GET', 'POST'])
def report_incident():
    if request.method == 'POST':
        try:
            incident = Incident(
                crrt_member_name=request.form.get('crrt_member_name', 'Unknown'),
                incident_date=request.form.get('incident_date', ''),
                incident_time=request.form.get('incident_time', ''),
                latitude=request.form.get('latitude', type=float) or 0.0,
                longitude=request.form.get('longitude', type=float) or 0.0,
                incident_type=request.form.get('incident_type', 'Unknown'),
                elephants_observed=request.form.get('elephants_observed', type=int) or 0,
                estimated_loss=request.form.get('estimated_loss', type=float) or 0.0,
                response_outcome=request.form.get('response_outcome', 'Unknown'),
                injuries_or_deaths=request.form.get('injuries_or_deaths', 'No one injured')
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
        
    except Exception as e:
        return f"Error exporting data: {str(e)}", 500

# Initialize database
with app.app_context():
    db.create_all()
    print("Database initialized successfully")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)