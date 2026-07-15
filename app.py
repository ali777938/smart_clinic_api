from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import hashlib
from datetime import datetime
from decimal import Decimal

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def get_db_connection():
    return mysql.connector.connect(
        host="bhmbj1m8nkpfvmeanijf-mysql.services.clever-cloud.com",
        user="uh6yw9wq8p3npzwq",
        password="PcoFoUA0rlIsB5Hb4VST",
        database="bhmbj1m8nkpfvmeanijf",
        port=3306
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
    specialty_id = data.get('specialty_id')
    consultation_fee = data.get('consultation_fee')

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
        
        if role == 'doctor':
            last_user_id = cursor.lastrowid
            if specialty_id and consultation_fee:
                cursor.execute(
                    "INSERT INTO doctors (user_id, specialty_id, consultation_fee) VALUES (%s, %s, %s)",
                    (last_user_id, specialty_id, consultation_fee)
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

        if user:
            final_user_id = user['id']
            
            # إذا كان المستخدم طبيباً، نجلب الـ id الخاص به من جدول الأطباء لتفادي مشكلة الشاشة الفارغة
            if user['role'] == 'doctor':
                cursor.execute("SELECT id FROM doctors WHERE user_id = %s", (user['id'],))
                doctor_data = cursor.fetchone()
                if doctor_data:
                    final_user_id = doctor_data['id']

            cursor.close()
            conn.close()

            return jsonify({
                "status": "success", 
                "role": user['role'],
                "user_id": final_user_id,
                "full_name": user['full_name'],
                "mail": user['mail']
            }), 200
        else:
            cursor.close()
            conn.close()
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
        
        processed_doctors = []
        for doc in res:
            if isinstance(doc['consultation_fee'], Decimal):
                doc['consultation_fee'] = float(doc['consultation_fee'])
            processed_doctors.append(doc)
            
        return jsonify({"status": "success", "doctors": processed_doctors})
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
        
        for appt in res:
            if isinstance(appt['appointment_date'], datetime):
                appt['appointment_date'] = appt['appointment_date'].strftime('%Y-%m-%d %H:%M:%S')
                
        return jsonify({"status": "success", "appointments": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/appointments/doctor/<int:doctor_id>', methods=['GET'])
def get_doctor_appointments(doctor_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT a.id, u.full_name AS patient_name, a.appointment_date, a.status, a.doctor_notes
            FROM appointments a
            JOIN users u ON a.patient_id = u.id
            WHERE a.doctor_id = %s
            ORDER BY a.appointment_date DESC
        """
        cursor.execute(query, (doctor_id,))
        res = cursor.fetchall()
        cursor.close()
        conn.close()
        
        for appt in res:
            if isinstance(appt['appointment_date'], datetime):
                appt['appointment_date'] = appt['appointment_date'].strftime('%Y-%m-%d %H:%M:%S')
                
        return jsonify({"status": "success", "appointments": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/appointments/update/<int:appointment_id>', methods=['POST'])
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
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)