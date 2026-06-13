from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Data storage (updated to include a 'phone' key)
drivers = [
    {
        "name": "Alice", 
        "pickup": "Downtown", 
        "dest": "Main Campus", 
        "time": "08:30", 
        "seats": 3, 
        "charge": "5.00",
        "phone": "+919876543210" # Added default phone for the sample driver
    },
]

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/rider')
def rider_page():
    return render_template('rider.html')

# 1. ADD RIDE ROUTE (Updated to capture the 'phone' field)
@app.route('/api/add_ride', methods=['POST'])
def add_ride():
    data = request.json
    try:
        drivers.append({
            "name": data.get('name'),
            "pickup": data.get('pickup'),
            "dest": data.get('dest'),
            "time": data.get('time'),
            "seats": data.get('seats'),
            "charge": data.get('charge'),
            "phone": data.get('phone') # NEW: Saves the driver's phone number
        })
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 2. MATCH RIDE ROUTE
@app.route('/api/match', methods=['POST'])
def find_matches():
    data = request.json
    # Clean rider inputs
    u_pickup = str(data.get('pickup', '')).strip().lower()
    u_dest = str(data.get('destination', '')).strip().lower()
    u_time = data.get('time')

    matches = []
    for d in drivers:
        d_pickup = str(d.get('pickup', '')).strip().lower()
        d_dest = str(d.get('dest', '')).strip().lower()
        
        # Check for Location Match (Case Insensitive)
        if d_pickup == u_pickup and d_dest == u_dest:
            if not u_time:
                matches.append(d)
                continue
                
            try:
                # Time window calculation
                t1 = datetime.strptime(u_time, '%H:%M')
                t2 = datetime.strptime(d['time'], '%H:%M')
                diff = abs((t1 - t2).total_seconds() / 60)
                
                if diff <= 60: # Match within 1 hour window
                    matches.append(d)
            except:
                # If time parsing fails, provide a fallback match based on location
                matches.append(d) 

    return jsonify(matches)

if __name__ == '__main__':
    # Running on default port 5000
    app.run(host='0.0.0.0', port=5000,debug=True)