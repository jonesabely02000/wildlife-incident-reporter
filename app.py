import json
from flask import request, jsonify

# Add these new routes before the existing ones

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