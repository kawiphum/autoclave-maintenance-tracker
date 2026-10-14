import sqlite3
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

DB_NAME = "maintenance.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_next_due(last_date_str, months):
    if not last_date_str:
        return None
    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        next_date = last_date + relativedelta(months=months)
        return next_date.strftime("%Y-%m-%d")
    except Exception:
        return None

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            brand_model TEXT,
            location TEXT,
            pm_freq_months INTEGER DEFAULT 6,
            cal_freq_months INTEGER DEFAULT 12,
            last_pm_date TEXT,
            next_pm_date TEXT,
            last_cal_date TEXT,
            next_cal_date TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            service_date TEXT NOT NULL,
            next_due_date TEXT NOT NULL,
            technician TEXT,
            result TEXT,
            remarks TEXT,
            FOREIGN KEY (equipment_id) REFERENCES equipments (id)
        )
    """)
    conn.commit()
    conn.close()

def add_equipment(code, name, eq_type, brand_model, location, pm_freq, cal_freq, last_pm, last_cal):
    conn = get_connection()
    cursor = conn.cursor()
    
    next_pm = calculate_next_due(last_pm, pm_freq)
    next_cal = calculate_next_due(last_cal, cal_freq)
    
    cursor.execute("""
        INSERT INTO equipments (
            equipment_code, name, type, brand_model, location, 
            pm_freq_months, cal_freq_months, last_pm_date, next_pm_date, last_cal_date, next_cal_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (code, name, eq_type, brand_model, location, pm_freq, cal_freq, last_pm, next_pm, last_cal, next_cal))
    
    conn.commit()
    conn.close()

def sync_equipment_latest_dates(equipment_id):
    """ฟังก์ชันคำนวณและอัปเดตวันล่าสุด/รอบถัดไปของเครื่องใหม่จากประวัติที่เหลืออยู่"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = ?", (equipment_id,))
    eq = cursor.fetchone()
    if not eq:
        conn.close()
        return

    # 1. หารอบ PM ล่าสุด
    cursor.execute("""
        SELECT service_date FROM service_records 
        WHERE equipment_id = ? AND task_type = 'PM' 
        ORDER BY service_date DESC LIMIT 1
    """, (equipment_id,))
    latest_pm = cursor.fetchone()
    last_pm_date = latest_pm["service_date"] if latest_pm else None
    next_pm_date = calculate_next_due(last_pm_date, eq["pm_freq_months"])

    # 2. หารอบ Calibration ล่าสุด
    cursor.execute("""
        SELECT service_date FROM service_records 
        WHERE equipment_id = ? AND task_type = 'Calibration' 
        ORDER BY service_date DESC LIMIT 1
    """, (equipment_id,))
    latest_cal = cursor.fetchone()
    last_cal_date = latest_cal["service_date"] if latest_cal else None
    next_cal_date = calculate_next_due(last_cal_date, eq["cal_freq_months"])

    cursor.execute("""
        UPDATE equipments 
        SET last_pm_date = ?, next_pm_date = ?, last_cal_date = ?, next_cal_date = ?
        WHERE id = ?
    """, (last_pm_date, next_pm_date, last_cal_date, next_cal_date, equipment_id))

    conn.commit()
    conn.close()

def log_service(equipment_id, task_type, service_date, technician, result, remarks):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = ?", (equipment_id,))
    row = cursor.fetchone()
    freq = row["pm_freq_months"] if task_type == "PM" else row["cal_freq_months"]
    next_due = calculate_next_due(service_date, freq)
    
    cursor.execute("""
        INSERT INTO service_records (equipment_id, task_type, service_date, next_due_date, technician, result, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (equipment_id, task_type, service_date, next_due, technician, result, remarks))
    conn.commit()
    conn.close()

    sync_equipment_latest_dates(equipment_id)
    return next_due

def update_service_record(record_id, service_date, technician, result, remarks):
    """แก้ไขข้อมูลประวัติ"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # ดึง equipment_id และ task_type เพื่อคำนวณ next_due_date ใหม่
    cursor.execute("SELECT equipment_id, task_type FROM service_records WHERE id = ?", (record_id,))
    rec = cursor.fetchone()
    if not rec:
        conn.close()
        return
        
    eq_id = rec["equipment_id"]
    task_type = rec["task_type"]
    
    cursor.execute("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = ?", (eq_id,))
    eq = cursor.fetchone()
    freq = eq["pm_freq_months"] if task_type == "PM" else eq["cal_freq_months"]
    next_due = calculate_next_due(service_date, freq)
    
    cursor.execute("""
        UPDATE service_records 
        SET service_date = ?, next_due_date = ?, technician = ?, result = ?, remarks = ?
        WHERE id = ?
    """, (service_date, next_due, technician, result, remarks, record_id))
    conn.commit()
    conn.close()

    sync_equipment_latest_dates(eq_id)

def delete_service_record(record_id):
    """ลบรายการประวัติ"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipment_id FROM service_records WHERE id = ?", (record_id,))
    rec = cursor.fetchone()
    if not rec:
        conn.close()
        return
    eq_id = rec["equipment_id"]
    
    cursor.execute("DELETE FROM service_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

    sync_equipment_latest_dates(eq_id)

def delete_equipment(equipment_id):
    """ลบเครื่องจักรและล้างประวัติการตรวจเช็คทั้งหมดของเครื่องนั้น"""
    conn = get_connection()
    cursor = conn.cursor()
    # 1. ลบประวัติการตรวจเช็คทั้งหมดที่ผูกกับเครื่องนี้ก่อน
    cursor.execute("DELETE FROM service_records WHERE equipment_id = ?", (equipment_id,))
    # 2. ลบข้อมูลเครื่องจักร
    cursor.execute("DELETE FROM equipments WHERE id = ?", (equipment_id,))
    conn.commit()
    conn.close()
def check_duplicate_service(equipment_id, task_type, service_date):
    """ตรวจสอบว่ามีการบันทึกงานประเภทเดียวกันในวันเดียวกันของเครื่องนี้ไปแล้วหรือไม่"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) AS cnt 
        FROM service_records 
        WHERE equipment_id = ? AND task_type = ? AND service_date = ?
    """, (equipment_id, task_type, service_date))
    row = cursor.fetchone()
    conn.close()
    return row["cnt"] > 0