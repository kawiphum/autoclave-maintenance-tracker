import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
from dateutil.relativedelta import relativedelta

def get_db_url():
    for key in ["DATABASE_URL", "database_url", "DB_URL", "db_url", "SUPABASE_DB_URL", "url", "uri"]:
        if key in st.secrets and isinstance(st.secrets[key], str):
            return st.secrets[key]
    
    for section in st.secrets.values():
        if isinstance(section, dict):
            for key in ["url", "uri", "DATABASE_URL", "database_url", "db_url"]:
                if key in section and isinstance(section[key], str):
                    return section[key]
            if "host" in section and "password" in section:
                user = section.get("user", section.get("username", "postgres"))
                pw = section.get("password")
                host = section.get("host")
                port = section.get("port", 5432)
                dbname = section.get("dbname", section.get("database", "postgres"))
                return f"postgresql://{user}:{pw}@{host}:{port}/{dbname}"

    def find_pg_string(d):
        for v in d.values():
            if isinstance(v, str) and (v.startswith("postgres://") or v.startswith("postgresql://")):
                return v
            elif isinstance(v, dict):
                res = find_pg_string(v)
                if res:
                    return res
        return None

    found_url = find_pg_string(st.secrets)
    if found_url:
        return found_url

    st.error("⚠️ ไม่พบข้อมูลเชื่อมต่อฐานข้อมูลใน Streamlit Secrets!")
    st.stop()

@st.cache_resource
def get_engine():
    db_url = get_db_url().strip()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

def get_connection():
    return get_engine().connect()

# รันคำสั่งสร้าง/ตรวจสอบตารางแค่ครั้งเดียวตอนเริ่มระบบ (ไม่รันซ้ำทุกครั้งที่กดปุ่ม)
@st.cache_resource
def init_db():
    conn = get_connection()
    try:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES ('hospital_name', 'ระบบติดตามรอบบำรุงรักษาเครื่องมือแพทย์')
            ON CONFLICT (setting_key) DO NOTHING;
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS branches (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );
        """))
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
        conn.execute(text("ALTER TABLE equipments ADD COLUMN IF NOT EXISTS branch TEXT DEFAULT 'สาขา A';"))
        conn.execute(text("UPDATE equipments SET branch = 'สาขา A' WHERE branch IS NULL OR branch = '';"))
        conn.execute(text("ALTER TABLE equipments DROP CONSTRAINT IF EXISTS equipments_equipment_code_key;"))

        branch_cnt = conn.execute(text("SELECT COUNT(*) FROM branches")).scalar()
        if branch_cnt == 0:
            for b in ["สาขา A", "สาขา B", "สาขา C"]:
                conn.execute(text("INSERT INTO branches (name) VALUES (:name) ON CONFLICT DO NOTHING"), {"name": b})
        
        conn.execute(text("""
            INSERT INTO branches (name)
            SELECT DISTINCT branch FROM equipments WHERE branch IS NOT NULL AND branch != ''
            ON CONFLICT DO NOTHING;
        """))

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
    return True

init_db()

# -------------------------------------------------------------
# ฟังก์ชันดึงข้อมูลพร้อม Cache (ทำให้สลับหน้าและพิมพ์ได้เร็วขึ้นมาก)
# -------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def get_hospital_name():
    conn = get_connection()
    try:
        res = conn.execute(text("SELECT setting_value FROM app_settings WHERE setting_key = 'hospital_name'")).fetchone()
        return res[0] if res else "ระบบติดตามรอบบำรุงรักษาเครื่องมือแพทย์"
    finally:
        conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def get_branches():
    conn = get_connection()
    try:
        rows = conn.execute(text("SELECT name FROM branches ORDER BY id ASC")).fetchall()
        return [r[0] for r in rows] if rows else ["สาขา A"]
    finally:
        conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def get_branch_data_cached(selected_branch):
    conn = get_connection()
    try:
        eq_query = text("SELECT * FROM equipments WHERE branch = :branch ORDER BY id ASC")
        df_eq = pd.read_sql_query(eq_query, conn, params={"branch": selected_branch})
        
        rec_query = text("""
            SELECT sr.* FROM service_records sr
            JOIN equipments eq ON sr.equipment_id = eq.id
            WHERE eq.branch = :branch
            ORDER BY sr.service_date DESC
        """)
        df_rec = pd.read_sql_query(rec_query, conn, params={"branch": selected_branch})
        return df_eq, df_rec
    finally:
        conn.close()

def clear_all_caches():
    get_hospital_name.clear()
    get_branches.clear()
    get_branch_data_cached.clear()

# -------------------------------------------------------------
# ฟังก์ชันบันทึกและแก้ไขข้อมูล (จะสั่งล้าง Cache เฉพาะเมื่อมีการเปลี่ยนแปลงข้อมูล)
# -------------------------------------------------------------
def update_hospital_name(new_name):
    conn = get_connection()
    try:
        conn.execute(text("""
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES ('hospital_name', :val)
            ON CONFLICT (setting_key) DO UPDATE SET setting_value = :val
        """), {"val": new_name})
        conn.commit()
        clear_all_caches()
    finally:
        conn.close()

def add_branch(branch_name):
    conn = get_connection()
    try:
        dup = conn.execute(text("SELECT id FROM branches WHERE name = :name"), {"name": branch_name}).fetchone()
        if dup:
            raise ValueError(f"มีสาขาชื่อ '{branch_name}' อยู่ในระบบแล้ว")
        conn.execute(text("INSERT INTO branches (name) VALUES (:name)"), {"name": branch_name})
        conn.commit()
        clear_all_caches()
    finally:
        conn.close()

def rename_branch(old_name, new_name):
    conn = get_connection()
    try:
        dup = conn.execute(text("SELECT id FROM branches WHERE name = :name"), {"name": new_name}).fetchone()
        if dup:
            raise ValueError(f"มีสาขาชื่อ '{new_name}' อยู่ในระบบแล้ว กรุณาใช้ชื่ออื่น")
        conn.execute(text("UPDATE branches SET name = :new WHERE name = :old"), {"new": new_name, "old": old_name})
        conn.execute(text("UPDATE equipments SET branch = :new WHERE branch = :old"), {"new": new_name, "old": old_name})
        conn.commit()
        clear_all_caches()
    finally:
        conn.close()

def delete_branch(branch_name):
    conn = get_connection()
    try:
        cnt = conn.execute(text("SELECT COUNT(*) FROM branches")).scalar()
        if cnt <= 1:
            raise ValueError("ไม่สามารถลบได้ ระบบต้องมีอย่างน้อย 1 สาขา")
        conn.execute(text("""
            DELETE FROM service_records WHERE equipment_id IN (
                SELECT id FROM equipments WHERE branch = :b
            )
        """), {"b": branch_name})
        conn.execute(text("DELETE FROM equipments WHERE branch = :b"), {"b": branch_name})
        conn.execute(text("DELETE FROM branches WHERE name = :b"), {"b": branch_name})
        conn.commit()
        clear_all_caches()
    finally:
        conn.close()

def add_equipment(code, name, eq_type, brand, location, pm_freq, cal_freq, last_pm, last_cal, branch="สาขา A"):
    conn = get_connection()
    try:
        check_q = text("SELECT id FROM equipments WHERE equipment_code = :code AND branch = :branch")
        dup = conn.execute(check_q, {"code": code, "branch": branch}).fetchone()
        if dup:
            raise ValueError(f"รหัสเครื่อง '{code}' มีอยู่ใน {branch} แล้ว กรุณาใช้รหัสอื่น")

        next_pm = str(datetime.strptime(last_pm, "%Y-%m-%d").date() + relativedelta(months=int(pm_freq))) if last_pm else None
        next_cal = str(datetime.strptime(last_cal, "%Y-%m-%d").date() + relativedelta(months=int(cal_freq))) if last_cal else None

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
        clear_all_caches()
    finally:
        conn.close()

def delete_equipment(eq_id):
    conn = get_connection()
    try:
        conn.execute(text("DELETE FROM service_records WHERE equipment_id = :id"), {"id": eq_id})
        conn.execute(text("DELETE FROM equipments WHERE id = :id"), {"id": eq_id})
        conn.commit()
        clear_all_caches()
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
    eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).fetchone()
    if not eq:
        return
    pm_freq, cal_freq = eq[0], eq[1]

    latest_pm = conn.execute(text("""
        SELECT service_date FROM service_records 
        WHERE equipment_id = :id AND task_type = 'PM' 
        ORDER BY service_date DESC LIMIT 1
    """), {"id": eq_id}).fetchone()

    if latest_pm and latest_pm[0]:
        l_pm = latest_pm[0]
        n_pm = str(datetime.strptime(l_pm, "%Y-%m-%d").date() + relativedelta(months=int(pm_freq)))
    else:
        l_pm, n_pm = None, None

    latest_cal = conn.execute(text("""
        SELECT service_date FROM service_records 
        WHERE equipment_id = :id AND task_type = 'Calibration' 
        ORDER BY service_date DESC LIMIT 1
    """), {"id": eq_id}).fetchone()

    if latest_cal and latest_cal[0]:
        l_cal = latest_cal[0]
        n_cal = str(datetime.strptime(l_cal, "%Y-%m-%d").date() + relativedelta(months=int(cal_freq)))
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
        clear_all_caches()
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
        clear_all_caches()
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
        clear_all_caches()
    finally:
        conn.close()
