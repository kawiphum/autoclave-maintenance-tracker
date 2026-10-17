import streamlit as st
from sqlalchemy import create_engine, text
from datetime import datetime
from dateutil.relativedelta import relativedelta

# สร้าง Engine เชื่อมต่อฐานข้อมูล
@st.cache_resource
def get_engine():
    db_url = st.secrets["DATABASE_URL"]
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, pool_pre_ping=True)

def get_connection():
    engine = get_engine()
    return engine.connect()

def init_db():
    """สร้างตารางและอัปเกรดโครงสร้างฐานข้อมูลให้รองรับระบบแยกสาขาอัตโนมัติ"""
    conn = get_connection()
    try:
        # 1. สร้างตาราง equipments (กรณีเพิ่งสร้างใหม่)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS equipments (
                id SERIAL PRIMARY KEY,
                equipment_code TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                brand_model TEXT,
                location TEXT,
                pm_freq_months INTEGER DEFAULT 6,
                cal_freq_months INTEGER DEFAULT 12,
                last_pm_date TEXT,
                next_pm_date TEXT,
                last_cal_date TEXT,
                next_cal_date TEXT,
                branch TEXT DEFAULT 'สาขา A'
            );
        """))

        # 2. อัปเกรดตารางเดิม: เพิ่มคอลัมน์ branch หากยังไม่มี และย้ายข้อมูลเก่าเข้า 'สาขา A'
        conn.execute(text("""
            ALTER TABLE equipments ADD COLUMN IF NOT EXISTS branch TEXT DEFAULT 'สาขา A';
        """))
        conn.execute(text("""
            UPDATE equipments SET branch = 'สาขา A' WHERE branch IS NULL OR branch = '';
        """))

        # 3. ปลดล็อกให้ต่างสาขาใช้รหัสเครื่อง (equipment_code) ซ้ำกันได้
        conn.execute(text("""
            ALTER TABLE equipments DROP CONSTRAINT IF EXISTS equipments_equipment_code_key;
        """))

        # 4. สร้างตาราง service_records
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS service_records (
                id SERIAL PRIMARY KEY,
                equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
                task_type TEXT NOT NULL,
                service_date TEXT NOT NULL,
                next_due_date TEXT,
                technician TEXT,
                result TEXT,
                remarks TEXT
            );
        """))
        conn.commit()
    except Exception as e:
        print(f"DB Init Warning: {e}")
    finally:
        conn.close()

# เรียกทำงานอัตโนมัติเมื่อเปิดแอป
init_db()

def add_equipment(code, name, eq_type, brand, location, pm_freq, cal_freq, last_pm, last_cal, branch="สาขา A"):
    conn = get_connection()
    try:
        # เช็กว่าในสาขาเดียวกันมีรหัสเครื่องนี้หรือยัง
        check_q = text("SELECT id FROM equipments WHERE equipment_code = :code AND branch = :branch")
        dup = conn.execute(check_q, {"code": code, "branch": branch}).fetchone()
        if dup:
            raise ValueError(f"รหัสเครื่อง '{code}' มีอยู่ใน {branch} แล้ว กรุณาใช้รหัสอื่น")

        next_pm = None
        if last_pm:
            dt_pm = datetime.strptime(last_pm, "%Y-%m-%d").date()
            next_pm = str(dt_pm + relativedelta(months=int(pm_freq)))

        next_cal = None
        if last_cal:
            dt_cal = datetime.strptime(last_cal, "%Y-%m-%d").date()
            next_cal = str(dt_cal + relativedelta(months=int(cal_freq)))

        insert_q = text("""
            INSERT INTO equipments 
            (equipment_code, name, type, brand_model, location, pm_freq_months, cal_freq_months, last_pm_date, next_pm_date, last_cal_date, next_cal_date, branch)
            VALUES (:code, :name, :type, :brand, :loc, :pm_f, :cal_f, :l_pm, :n_pm, :l_cal, :n_cal, :branch)
        """)
        conn.execute(insert_q, {
            "code": code, "name": name, "type": eq_type, "brand": brand, "loc": location,
            "pm_f": pm_freq, "cal_f": cal_freq, "l_pm": last_pm, "n_pm": next_pm,
            "l_cal": last_cal, "n_cal": next_cal, "branch": branch
        })
        conn.commit()
    finally:
        conn.close()

def delete_equipment(eq_id):
    conn = get_connection()
    try:
        conn.execute(text("DELETE FROM service_records WHERE equipment_id = :id"), {"id": eq_id})
        conn.execute(text("DELETE FROM equipments WHERE id = :id"), {"id": eq_id})
        conn.commit()
    finally:
        conn.close()

def check_duplicate_service(eq_id, task_type, service_date):
    conn = get_connection()
    try:
        q = text("""
            SELECT id FROM service_records 
            WHERE equipment_id = :eq_id AND task_type = :t_type AND service_date = :s_date
        """)
        res = conn.execute(q, {"eq_id": eq_id, "t_type": task_type, "s_date": service_date}).fetchone()
        return res is not None
    finally:
        conn.close()

def recalculate_equipment_dates(conn, eq_id):
    """คำนวณวันตรวจล่าสุดและรอบถัดไปของเครื่องจักรใหม่จากประวัติทั้งหมด"""
    eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).fetchone()
    if not eq:
        return
    pm_freq, cal_freq = eq[0], eq[1]

    # หาประวัติ PM ล่าสุด
    latest_pm = conn.execute(text("""
        SELECT service_date FROM service_records 
        WHERE equipment_id = :id AND task_type = 'PM' 
        ORDER BY service_date DESC LIMIT 1
    """), {"id": eq_id}).fetchone()

    if latest_pm and latest_pm[0]:
        l_pm = latest_pm[0]
        dt_pm = datetime.strptime(l_pm, "%Y-%m-%d").date()
        n_pm = str(dt_pm + relativedelta(months=int(pm_freq)))
    else:
        l_pm, n_pm = None, None

    # หาประวัติ Calibration ล่าสุด
    latest_cal = conn.execute(text("""
        SELECT service_date FROM service_records 
        WHERE equipment_id = :id AND task_type = 'Calibration' 
        ORDER BY service_date DESC LIMIT 1
    """), {"id": eq_id}).fetchone()

    if latest_cal and latest_cal[0]:
        l_cal = latest_cal[0]
        dt_cal = datetime.strptime(l_cal, "%Y-%m-%d").date()
        n_cal = str(dt_cal + relativedelta(months=int(cal_freq)))
    else:
        l_cal, n_cal = None, None

    conn.execute(text("""
        UPDATE equipments 
        SET last_pm_date = :l_pm, next_pm_date = :n_pm,
            last_cal_date = :l_cal, next_cal_date = :n_cal
        WHERE id = :id
    """), {"l_pm": l_pm, "n_pm": n_pm, "l_cal": l_cal, "n_cal": n_cal, "id": eq_id})

def log_service(eq_id, task_type, service_date, technician, result, remarks):
    conn = get_connection()
    try:
        eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).fetchone()
        freq = eq[0] if task_type == "PM" else eq[1]
        
        dt_service = datetime.strptime(service_date, "%Y-%m-%d").date()
        next_due = str(dt_service + relativedelta(months=int(freq)))

        conn.execute(text("""
            INSERT INTO service_records (equipment_id, task_type, service_date, next_due_date, technician, result, remarks)
            VALUES (:eq_id, :t_type, :s_date, :n_due, :tech, :res, :rem)
        """), {
            "eq_id": eq_id, "t_type": task_type, "s_date": service_date,
            "n_due": next_due, "tech": technician, "res": result, "rem": remarks
        })
        
        recalculate_equipment_dates(conn, eq_id)
        conn.commit()
        return next_due
    finally:
        conn.close()

def update_service_record(record_id, new_date, new_tech, new_res, new_rem):
    conn = get_connection()
    try:
        rec = conn.execute(text("SELECT equipment_id, task_type FROM service_records WHERE id = :id"), {"id": record_id}).fetchone()
        if not rec:
            return
        eq_id, task_type = rec[0], rec[1]
        
        eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).fetchone()
        freq = eq[0] if task_type == "PM" else eq[1]
        
        dt_service = datetime.strptime(new_date, "%Y-%m-%d").date()
        next_due = str(dt_service + relativedelta(months=int(freq)))

        conn.execute(text("""
            UPDATE service_records 
            SET service_date = :s_date, next_due_date = :n_due, technician = :tech, result = :res, remarks = :rem
            WHERE id = :id
        """), {"s_date": new_date, "n_due": next_due, "tech": new_tech, "res": new_res, "rem": new_rem, "id": record_id})

        recalculate_equipment_dates(conn, eq_id)
        conn.commit()
    finally:
        conn.close()

def delete_service_record(record_id):
    conn = get_connection()
    try:
        rec = conn.execute(text("SELECT equipment_id FROM service_records WHERE id = :id"), {"id": record_id}).fetchone()
        eq_id = rec[0] if rec else None

        conn.execute(text("DELETE FROM service_records WHERE id = :id"), {"id": record_id})
        
        if eq_id:
            recalculate_equipment_dates(conn, eq_id)
        conn.commit()
    finally:
        conn.close()
