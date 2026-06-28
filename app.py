from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import hashlib
from datetime import datetime

app = Flask(__name__)
CORS(app)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="smart_clinic"
    )

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Welcome to Smart Clinic API!"})

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    full_name = data.get('full_name')
    mail = data.get('mail')
    password = data.get('password')
    role = data.get('role')

    if not all([full_name, mail, password, role]):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    if role not in ['doctor', 'patient']:
        return jsonify({"status": "error", "message": "Invalid role"}), 400

    hashed_pwd = hash_password(password)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE mail = %s", (mail,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Email already exists"}), 400
            
        cursor.execute(
            "INSERT INTO users (full_name, mail, password, role) VALUES (%s, %s, %s, %s)",
            (full_name, mail, hashed_pwd, role)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    mail = data.get('mail')
    password = data.get('password')

    if not mail or not password:
        return jsonify({"status": "error", "message": "Email and password are required"}), 400

    hashed_pwd = hash_password(password)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, full_name, mail, role FROM users WHERE mail = %s AND password = %s",
            (mail, hashed_pwd)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return jsonify({"status": "success", "user": user}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/specialties', methods=['GET'])
def get_specialties():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM specialties")
        res = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "specialties": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/doctors', methods=['GET'])
def get_doctors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT d.id AS doctor_id, u.full_name, s.name AS specialty, d.consultation_fee 
            FROM doctors d
            JOIN users u ON d.user_id = u.id
            JOIN specialties s ON d.specialty_id = s.id
        """
        cursor.execute(query)
        res = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "doctors": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/appointments/book', methods=['POST'])
def book_appointment():
    data = request.json
    patient_id = data.get('patient_id')
    doctor_id = data.get('doctor_id')
    appointment_date = data.get('appointment_date')
    if not all([patient_id, doctor_id, appointment_date]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO appointments (patient_id, doctor_id, appointment_date) VALUES (%s, %s, %s)",
            (patient_id, doctor_id, appointment_date)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Appointment booked successfully"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/patient/appointments/<int:patient_id>', methods=['GET'])
def get_patient_appointments(patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT a.id, u.full_name AS doctor_name, s.name AS specialty, a.appointment_date, a.status, a.doctor_notes
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN users u ON d.user_id = u.id
            JOIN specialties s ON d.specialty_id = s.id
            WHERE a.patient_id = %s
            ORDER BY a.appointment_date DESC
        """
        cursor.execute(query, (patient_id,))
        res = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "appointments": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/doctor/appointments/<int:user_id>', methods=['GET'])
def get_doctor_appointments(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM doctors WHERE user_id = %s", (user_id,))
        doctor = cursor.fetchone()
        if not doctor:
            return jsonify({"status": "error", "message": "Doctor record not found"}), 404
            
        doctor_id = doctor['id']
        today = datetime.now().strftime('%Y-%m-%d')
        
        query = """
            SELECT a.id, u.full_name AS patient_name, a.appointment_date, a.status, a.doctor_notes
            FROM appointments a
            JOIN users u ON a.patient_id = u.id
            WHERE a.doctor_id = %s AND DATE(a.appointment_date) = %s
            ORDER BY a.appointment_date ASC
        """
        cursor.execute(query, (doctor_id, today))
        res = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "appointments": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/appointments/update/<int:appointment_id>', methods=['PUT'])
def update_appointment(appointment_id):
    data = request.json
    status = data.get('status')
    doctor_notes = data.get('doctor_notes', None)

    if not status or status not in ['confirmed', 'completed', 'cancelled']:
        return jsonify({"status": "error", "message": "Invalid or missing status"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if doctor_notes:
            cursor.execute(
                "UPDATE appointments SET status = %s, doctor_notes = %s WHERE id = %s",
                (status, doctor_notes, appointment_id)
            )
        else:
            cursor.execute(
                "UPDATE appointments SET status = %s WHERE id = %s",
                (status, appointment_id)
            )
            
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Appointment updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)