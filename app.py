import sys
import asyncio
import math  # Used for coordinate distance math calculations
import os
from bson.objectid import ObjectId

# 🔥 CRITICAL FIX: Prevent 'OSError: [WinError 10038]' on Windows with Python 3.14+
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
import certifi
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Upgraded secret key layout to ensure stable secure Flask Session cookie management tracking
app.config['SECRET_KEY'] = 'campus_pool_secure_key_2026'

# Initialize SocketIO to allow real-time WebSocket communication
socketio = SocketIO(app, cors_allowed_origins="*")

# =====================================================================
# MONGO LIVE CLUSTER SYNC DIRECTORY
# =====================================================================
MONGO_URI = "mongodb+srv://carpool_admin:CarpoolPro123@cluster0.k9mo670.mongodb.net/carpool_db?retryWrites=true&w=majority&appName=Cluster0&connectTimeoutMS=30000&socketTimeoutMS=30000"

try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['carpool_db']
    drivers_collection = db['drivers']
    bookings_collection = db['bookings']
    users_collection = db['users']  # 🔥 Added authentication collection tracking reference
    print("🚀 Successfully connected to MongoDB Atlas Cluster!")
except Exception as e:
    print(f"❌ Connection error: {e}")


# =====================================================================
# 🧭 GEOSPATIAL HELPER UTILITIES
# =====================================================================
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Computes the great-circle distance between two GPS coordinates
    on the Earth's surface using the Haversine formula.
    """
    try:
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Haversine calculation
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        km = 6371 * c  # Earth radius multiplier
        return km
    except Exception:
        return float('inf')  # Return infinity if values are invalid numbers


# =====================================================================
# APPLICATION ENDPOINTS (ROUTING)
# =====================================================================

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/rider')
def rider_page():
    return render_template('rider.html')


# =====================================================================
# NEW: DRIVER REGISTRATION & AUTHENTICATION ENDPOINTS
# =====================================================================

@app.route('/api/driver/signup', methods=['POST'])
def driver_signup():
    try:
        data = request.json or {}
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', ''))
        phone = str(data.get('phone', '')).strip()

        if not username or not password or not phone:
            return jsonify({"status": "error", "message": "All fields are mandatory!"}), 400

        if users_collection.find_one({"username": username}):
            return jsonify({"status": "error", "message": "Username already exists!"}), 400

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            "username": username,
            "password": hashed_password,
            "phone": phone
        })
        return jsonify({"status": "success", "message": "Account created! Please log in."}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/driver/login', methods=['POST'])
def driver_login():
    try:
        data = request.json or {}
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', ''))

        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user['password'], password):
            session['driver_username'] = username
            session['driver_phone'] = user.get('phone', '')
            return jsonify({"status": "success", "message": "Login successful!"}), 200
        
        return jsonify({"status": "error", "message": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/driver/logout', methods=['GET'])
def driver_logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


# =====================================================================
# NEW: LIVE DRIVER PORTAL TELEMETRY DATA AGGREGATION
# =====================================================================

@app.route('/api/driver/dashboard_data', methods=['GET'])
def get_dashboard_data():
    if 'driver_username' not in session:
        return jsonify({"status": "error", "message": "Unauthorized access. Please log in."}), 401
    
    try:
        driver_phone = session.get('driver_phone')
        
        # Find the most recent active ride published by this matching driver's phone number
        active_ride = drivers_collection.find_one({"phone": driver_phone}, sort=[("_id", -1)])
        
        if not active_ride:
            return jsonify({
                "has_active_ride": False,
                "riders": [],
                "total_earnings": 0
            }), 200

        ride_id = active_ride['_id']
        
        # Query bookings associated with the active ride object identifier
        bookings = list(bookings_collection.find({"ride_id": ObjectId(ride_id)}))
        
        # Handle configuration parameters safely to prevent math evaluation anomalies
        try:
            charge_per_seat = float(active_ride.get('charge', 0))
        except Exception:
            charge_per_seat = 0.0
            
        total_earnings = len(bookings) * charge_per_seat
        
        # Format layout response parameters to match your frontend dynamic dashboard layout variables
        formatted_riders = []
        for b in bookings:
            formatted_riders.append({
                "name": b.get('rider_name', b.get('riderName', 'Unknown Rider')),
                "phone": b.get('rider_phone', b.get('riderPhone', ''))
            })

        return jsonify({
            "has_active_ride": True,
            "location": active_ride.get('pickup', ''),
            "destination": active_ride.get('dest', ''),
            "seats_left": active_ride.get('seats', 0),
            "total_earnings": total_earnings,
            "riders": formatted_riders
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# =====================================================================
# EXISTING CORE API ENDPOINTS (PRESERVED EXCLUSIVELY)
# =====================================================================

@app.route('/api/add_ride', methods=['POST'])
def add_ride():
    data = request.json or {}
    try:
        new_driver = {
            "name": str(data.get('driverName', '')).strip(),
            "pickup": str(data.get('location', '')).strip(), 
            "dest": str(data.get('destination', '')).strip(),          
            "time": str(data.get('departureTime', '')).strip(),
            "seats": int(data.get('seats', 3)),  # Kept as integer for structural arithmetic increments
            "charge": str(data.get('petrolCharge', '')).strip(),
            "phone": str(data.get('driverPhone', '')).strip(),
            # 🛠️ CAPTURING DRIVER LAT/LNG (sent from your driver configuration app)
            "current_lat": data.get('lat'),
            "current_lng": data.get('lng')
        }
        
        result = drivers_collection.insert_one(new_driver)
        return jsonify({
            "status": "success", 
            "message": "Ride saved successfully!",
            "ride_id": str(result.inserted_id)
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Cloud Write Failed: {str(e)}"}), 400


@app.route('/api/match', methods=['POST'])
def find_matches():
    try:
        data = request.json or {}
        
        u_pickup = str(data.get('pickup', '')).strip().lower()
        u_dest = str(data.get('destination', '')).strip().lower()
        u_time = str(data.get('departureTime', '')).strip()

        r_lat = data.get('lat')
        r_lng = data.get('lng')

        print(f"🔍 Strict Triple-Match Scan: Pickup='{u_pickup}', Dest='{u_dest}', Time='{u_time}'")

        # Fetch only drivers who have available seats remaining
        all_drivers = list(drivers_collection.find({"seats": {"$gt": 0}}))
        matches = []
        
        # 📍 RADIUS THRESHOLD: Matches drivers within a 10km limit for local pickup coordinates
        MAX_RADIUS_KM = 10.0 

        for d in all_drivers:
            d_pickup = str(d.get('pickup', '')).strip().lower()
            d_dest = str(d.get('dest', '')).strip().lower()
            d_time = str(d.get('time', '')).strip()
            
            # 🎯 CRITICAL RULE 1: STRICT DESTINATION MATCH
            if u_dest not in d_dest and d_dest not in u_dest:
                continue

            # ⏰ CRITICAL RULE 2: STRICT TIME MATCH
            if u_time and d_time and u_time != d_time:
                continue

            # 📍 CRITICAL RULE 3: PICKUP VALIDATION (GPS Radius with Text Fallback)
            is_pickup_matched = False
            
            # Check GPS coordinates first if available
            d_lat = d.get('current_lat')
            d_lng = d.get('current_lng')
            if r_lat is not None and r_lng is not None and d_lat is not None and d_lng is not None:
                distance = calculate_distance(r_lat, r_lng, d_lat, d_lng)
                if distance <= MAX_RADIUS_KM:
                    is_pickup_matched = True

            # Fallback to Text comparison for pickup if GPS didn't catch it
            if not is_pickup_matched and u_pickup and d_pickup:
                if u_pickup in d_pickup or d_pickup in u_pickup:
                    is_pickup_matched = True

            # If pickup doesn't match via GPS or Text, skip this driver entirely
            if not is_pickup_matched:
                continue

            # If all validations pass, map the object data format safely for the frontend
            d['id'] = str(d['_id'])
            del d['_id']
            matches.append(d)

        print(f"✅ Filter Complete: Found {len(matches)} matching routes passing all criteria.")
        return jsonify(matches), 200

    except Exception as e:
        print(f"❌ Match Route System Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/book_seat', methods=['POST'])
def book_seat():
    data = request.json or {}
    ride_id = data.get('ride_id')
    rider_name = str(data.get('riderName', 'Anonymous Rider')).strip()
    rider_phone = str(data.get('riderPhone', '')).strip()

    if not ride_id:
        return jsonify({"status": "error", "message": "Missing ride reference identification parameters"}), 400

    try:
        # Check active seat parameters dynamically
        ride = drivers_collection.find_one({"_id": ObjectId(ride_id)})
        if not ride:
            return jsonify({"status": "error", "message": "Ride assignment instance not found"}), 404
            
        current_seats = int(ride.get('seats', 0))
        if current_seats <= 0:
            return jsonify({"status": "error", "message": "No seats available! Vehicle is fully packed."}), 400

        # Decrement operational available seat balances cleanly inside MongoDB
        drivers_collection.update_one(
            {"_id": ObjectId(ride_id)},
            {"$inc": {"seats": -1}}
        )

        # Log details to dedicated roster mapping matrix
        bookings_collection.insert_one({
            "ride_id": ObjectId(ride_id),
            "rider_name": rider_name,
            "rider_phone": rider_phone
        })

        return jsonify({"status": "success", "message": "Seat secured successfully! 🎉"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/my_riders/<ride_id>', methods=['GET'])
def get_my_riders(ride_id):
    try:
        if not ride_id or ride_id == "null":
            return jsonify([]), 200
        # Fetch allocations corresponding exactly with active driver unique key ids
        all_bookings = list(bookings_collection.find({"sample_id": ObjectId(ride_id)}, {"_id": 0, "ride_id": 0}))
        # Alternative structural optimization check for mixed inputs
        if not all_bookings:
            all_bookings = list(bookings_collection.find({"ride_id": ObjectId(ride_id)}, {"_id": 0, "ride_id": 0}))
        return jsonify(all_bookings), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# =====================================================================
# ANALYTICS DASHBOARD ROUTE
# =====================================================================
@app.route('/dashboard')
def dashboard():
    try:
        # Safe aggregation framework matching fields exactly to the insertion collection maps
        driver_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_drivers": {"$sum": 1},
                    "total_value_pool": {"$sum": {"$toDouble": "$charge"}},
                    "avg_seats": {"$avg": {"$toDouble": "$seats"}},
                    "avg_charge": {"$avg": {"$toDouble": "$charge"}}
                }
            }
        ]
        
        stats_result = list(drivers_collection.aggregate(driver_pipeline))
        
        if stats_result and len(stats_result) > 0:
            metrics = stats_result[0]
        else:
            metrics = {
                "total_drivers": 0,
                "total_value_pool": 0,
                "avg_seats": 0,
                "avg_charge": 0
            }
            
        # Top campus destinations aggregation based on "dest" field values
        dest_pipeline = [
            {"$group": {"_id": "$dest", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        top_destinations = list(drivers_collection.aggregate(dest_pipeline))

        return render_template('dashboard.html', metrics=metrics, top_destinations=top_destinations)
        
    except Exception as e:
        print(f"❌ Dashboard Pipeline Error: {e}")
        fallback_metrics = {"total_drivers": 0, "total_value_pool": 0, "avg_seats": 0, "avg_charge": 0}
        return render_template('dashboard.html', metrics=fallback_metrics, top_destinations=[])


# =====================================================================
# 🔥 WEBSOCKET EVENTS FOR REAL-TIME TRACKING
# =====================================================================

@socketio.on('update_location')
def handle_location_update(data):
    """
    Listens for live GPS data from the driver's device and immediately 
    broadcast it to the connected rider tracking them.
    """
    emit('location_broadcast', data, broadcast=True)


if __name__ == '__main__':
    # CRITICAL: Using socketio.run instead of app.run to support WebSocket streaming concurrently
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)