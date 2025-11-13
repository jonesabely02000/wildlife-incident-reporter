from flask import Flask, render_template, request, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)

# Database configuration
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///incidents.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    submission_time = db.Column(db.String(50), default=lambda: datetime.now().isoformat())

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/report', methods=['GET', 'POST'])
def report_incident():
    if request.method == 'POST':
        incident = Incident(
            crrt_member_name=request.form.get('crrt_member_name'),
            incident_date=request.form.get('incident_date'),
            incident_time=request.form.get('incident_time'),
            latitude=request.form.get('latitude', type=float),
            longitude=request.form.get('longitude', type=float),
            incident_type=request.form.get('incident_type'),
            elephants_observed=request.form.get('elephants_observed', type=int),
            estimated_loss=request.form.get('estimated_loss', type=float)
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
    return "Export will be added later"

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)