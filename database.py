import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
from dateutil.relativedelta import relativedelta

def get_db_url():
    for key in ["DATABASE_URL", "database_url", "DB_URL", "db_url", "SUPABASE_DB_URL", "url", "uri"]:
        if key in st.secrets and isinstance(st.secrets[key], str): return st.secrets[key]
    for section in st.secrets.values():
        if isinstance(section, dict):
            for key in ["url", "uri", "DATABASE_URL", "database_url", "db_url"]:
                if key in section and isinstance(section[key], str): return section[key]
            if "host" in section and "password" in section:
                return f"postgresql://{section.get('user', 'postgres')}:{section.get('password')}@{section.get('host')}:{section.get('port', 5432)}/{section.get('dbname', 'postgres')}"
    def find_pg_string(d):
        for v in d.values():
            if isinstance(v, str) and (v.startswith("postgres://") or v.startswith("postgresql://")): return v
            elif isinstance(v, dict):
                res = find_pg_string(v)
                if res: return res
        return None
    found_url = find_pg_string(st.secrets)
    if found_url: return found_url
    st.error("ไม่พบข้อมูลเชื่อมต่อฐานข้อมูล")
    st.stop()

@st.cache_resource
def get_engine():
    db_url = get_db_url().strip()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

def get_connection():
    return get_engine().connect()

@st.cache_resource
def init_db():
    conn = get_connection()
    try:
        # ตารางระบบ
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL);"))
        conn.execute(text("INSERT INTO app_settings (setting_key, setting_value) VALUES ('hospital_name', 'ระบบติดตามรอบบำรุงรักษาเครื่องมือแพทย์') ON CONFLICT (setting_key) DO NOTHING;"))
        
        # ตารางผู้ใช้งาน (Users)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                branch TEXT
            );
        """))
        # สร้างบัญชีเจ้าของระบบอัตโนมัติ (Super Admin)
        conn.execute(text("INSERT INTO users (username, password, role, branch) VALUES ('owner', 'owner1234', 'super_admin', 'สาขาส่วนกลาง') ON CONFLICT (username) DO NOTHING;"))

        # ตารางสาขา
        conn.execute(text("CREATE TABLE IF NOT EXISTS branches (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);"))
        
        # ตารางอุปกรณ์
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS equipments (
                id SERIAL PRIMARY KEY, equipment_code TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL,
                brand_model TEXT, location TEXT, pm_freq_months INTEGER DEFAULT 6, cal_freq_months INTEGER DEFAULT 12,
                last_pm_date TEXT, next_pm_date TEXT, last_cal_date TEXT, next_cal_date TEXT, branch TEXT DEFAULT 'สาขาส่วนกลาง'
            );
        """))
        conn.execute(text("ALTER TABLE equipments DROP CONSTRAINT IF EXISTS equipments_equipment_code_key;"))

        # สร้างสาขาเริ่มต้น
        branch_cnt = conn.execute(text("SELECT COUNT(*) FROM branches")).scalar()
        if branch_cnt == 0:
            conn.execute(text("INSERT INTO branches (name) VALUES ('สาขาส่วนกลาง') ON CONFLICT DO NOTHING"))
        conn.execute(text("INSERT INTO branches (name) SELECT DISTINCT branch FROM equipments WHERE branch IS NOT NULL AND branch != '' ON CONFLICT DO NOTHING;"))

        # ตารางประวัติ
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS service_records (
                id SERIAL PRIMARY KEY, equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
                task_type TEXT NOT NULL, service_date TEXT NOT NULL, next_due_date TEXT,
                technician TEXT, result TEXT, remarks TEXT
            );
        """))
        conn.commit()
    except Exception as e: print(f"DB Init Warning: {e}")
    finally: conn.close()
    return True

init_db()

# -------------------------------------------------------------
# Authentication Functions (ระบบสมาชิก)
# -------------------------------------------------------------
def login_user(username, password):
    conn = get_connection()
    try:
        res = conn.execute(text("SELECT role, branch FROM users WHERE username=:u AND password=:p"), {"u": username, "p": password}).fetchone()
        if res: return {"role": res[0], "branch": res[1]}
        return None
    finally: conn.close()

def register_user(username, password, branch):
    conn = get_connection()
    try:
        res = conn.execute(text("SELECT id FROM users WHERE username=:u"), {"u": username}).fetchone()
        if res: return False # ซ้ำ
        conn.execute(text("INSERT INTO users (username, password, role, branch) VALUES (:u, :p, 'user', :b)"), {"u": username, "p": password, "b": branch})
        conn.commit()
        return True
    finally: conn.close()

def get_all_users():
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT id, username, role, branch FROM users ORDER BY id ASC", conn)
    finally: conn.close()

def update_user_role_branch(user_id, new_role, new_branch):
    conn = get_connection()
    try:
        conn.execute(text("UPDATE users SET role=:r, branch=:b WHERE id=:id"), {"r": new_role, "b": new_branch, "id": user_id})
        conn.commit()
    finally: conn.close()

def delete_user(user_id):
    conn = get_connection()
    try:
        conn.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
        conn.commit()
    finally: conn.close()

# -------------------------------------------------------------
# Data Functions
# -------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def get_hospital_name():
    conn = get_connection()
    try:
        res = conn.execute(text("SELECT setting_value FROM app_settings WHERE setting_key = 'hospital_name'")).fetchone()
        return res[0] if res else "ระบบติดตามบำรุงรักษา"
    finally: conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def get_branches():
    conn = get_connection()
    try:
        rows = conn.execute(text("SELECT name FROM branches ORDER BY id ASC")).fetchall()
        return [r[0] for r in rows] if rows else ["สาขาส่วนกลาง"]
    finally: conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def get_branch_data_cached(selected_branch):
    conn = get_connection()
    try:
        df_eq = pd.read_sql_query(text("SELECT * FROM equipments WHERE branch = :branch ORDER BY id ASC"), conn, params={"branch": selected_branch})
        df_rec = pd.read_sql_query(text("SELECT sr.* FROM service_records sr JOIN equipments eq ON sr.equipment_id = eq.id WHERE eq.branch = :branch ORDER BY sr.service_date DESC"), conn, params={"branch": selected_branch})
        return df_eq, df_rec
    finally: conn.close()

def clear_all_caches():
    get_hospital_name.clear()
    get_branches.clear()
    get_branch_data_cached.clear()

def update_hospital_name(new_name):
    conn = get_connection()
    try:
        conn.execute(text("UPDATE app_settings SET setting_value = :val WHERE setting_key = 'hospital_name'"), {"val": new_name})
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def add_branch(branch_name):
    conn = get_connection()
    try:
        dup = conn.execute(text("SELECT id FROM branches WHERE name = :name"), {"name": branch_name}).fetchone()
        if dup: raise ValueError(f"สาขา '{branch_name}' มีอยู่แล้ว")
        conn.execute(text("INSERT INTO branches (name) VALUES (:name)"), {"name": branch_name})
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def rename_branch(old_name, new_name):
    conn = get_connection()
    try:
        dup = conn.execute(text("SELECT id FROM branches WHERE name = :name"), {"name": new_name}).fetchone()
        if dup: raise ValueError("ชื่อสาขานี้มีอยู่แล้ว")
        conn.execute(text("UPDATE branches SET name = :new WHERE name = :old"), {"new": new_name, "old": old_name})
        conn.execute(text("UPDATE equipments SET branch = :new WHERE branch = :old"), {"new": new_name, "old": old_name})
        conn.execute(text("UPDATE users SET branch = :new WHERE branch = :old"), {"new": new_name, "old": old_name})
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def delete_branch(branch_name):
    conn = get_connection()
    try:
        cnt = conn.execute(text("SELECT COUNT(*) FROM branches")).scalar()
        if cnt <= 1: raise ValueError("ไม่สามารถลบได้ ต้องมีอย่างน้อย 1 สาขา")
        conn.execute(text("DELETE FROM service_records WHERE equipment_id IN (SELECT id FROM equipments WHERE branch = :b)"), {"b": branch_name})
        conn.execute(text("DELETE FROM equipments WHERE branch = :b"), {"b": branch_name})
        conn.execute(text("DELETE FROM branches WHERE name = :b"), {"b": branch_name})
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def add_equipment(code, name, eq_type, brand, location, pm_freq, cal_freq, last_pm, last_cal, branch):
    conn = get_connection()
    try:
        dup = conn.execute(text("SELECT id FROM equipments WHERE equipment_code = :code AND branch = :branch"), {"code": code, "branch": branch}).fetchone()
        if dup: raise ValueError("รหัสเครื่องซ้ำในสาขานี้")
        next_pm = str(datetime.strptime(last_pm, "%Y-%m-%d").date() + relativedelta(months=int(pm_freq))) if last_pm else None
        next_cal = str(datetime.strptime(last_cal, "%Y-%m-%d").date() + relativedelta(months=int(cal_freq))) if last_cal else None
        conn.execute(text("""
            INSERT INTO equipments (equipment_code, name, type, brand_model, location, pm_freq_months, cal_freq_months, last_pm_date, next_pm_date, last_cal_date, next_cal_date, branch)
            VALUES (:code, :name, :type, :brand, :loc, :pm_f, :cal_f, :l_pm, :n_pm, :l_cal, :n_cal, :branch)
        """), {"code": code, "name": name, "type": eq_type, "brand": brand, "loc": location, "pm_f": pm_freq, "cal_f": cal_freq, "l_pm": last_pm, "n_pm": next_pm, "l_cal": last_cal, "n_cal": next_cal, "branch": branch})
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def delete_equipment(eq_id):
    conn = get_connection()
    try:
        conn.execute(text("DELETE FROM service_records WHERE equipment_id = :id"), {"id": eq_id})
        conn.execute(text("DELETE FROM equipments WHERE id = :id"), {"id": eq_id})
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def check_duplicate_service(eq_id, task_type, service_date):
    conn = get_connection()
    try:
        res = conn.execute(text("SELECT id FROM service_records WHERE equipment_id = :eq_id AND task_type = :t_type AND service_date = :s_date"), {"eq_id": eq_id, "t_type": task_type, "s_date": service_date}).fetchone()
        return res is not None
    finally: conn.close()

def recalculate_equipment_dates(conn, eq_id):
    eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).fetchone()
    if not eq: return
    latest_pm = conn.execute(text("SELECT service_date FROM service_records WHERE equipment_id = :id AND task_type = 'PM' ORDER BY service_date DESC LIMIT 1"), {"id": eq_id}).fetchone()
    n_pm = str(datetime.strptime(latest_pm[0], "%Y-%m-%d").date() + relativedelta(months=int(eq[0]))) if latest_pm and latest_pm[0] else None
    l_pm = latest_pm[0] if latest_pm else None
    latest_cal = conn.execute(text("SELECT service_date FROM service_records WHERE equipment_id = :id AND task_type = 'Calibration' ORDER BY service_date DESC LIMIT 1"), {"id": eq_id}).fetchone()
    n_cal = str(datetime.strptime(latest_cal[0], "%Y-%m-%d").date() + relativedelta(months=int(eq[1]))) if latest_cal and latest_cal[0] else None
    l_cal = latest_cal[0] if latest_cal else None
    conn.execute(text("UPDATE equipments SET last_pm_date = :l_pm, next_pm_date = :n_pm, last_cal_date = :l_cal, next_cal_date = :n_cal WHERE id = :id"), {"l_pm": l_pm, "n_pm": n_pm, "l_cal": l_cal, "n_cal": n_cal, "id": eq_id})

def log_service(eq_id, task_type, service_date, technician, result, remarks):
    conn = get_connection()
    try:
        eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).fetchone()
        freq = eq[0] if task_type == "PM" else eq[1]
        next_due = str(datetime.strptime(service_date, "%Y-%m-%d").date() + relativedelta(months=int(freq)))
        conn.execute(text("INSERT INTO service_records (equipment_id, task_type, service_date, next_due_date, technician, result, remarks) VALUES (:eq_id, :t_type, :s_date, :n_due, :tech, :res, :rem)"), {
            "eq_id": eq_id, "t_type": task_type, "s_date": service_date, "n_due": next_due, "tech": technician, "res": result, "rem": remarks})
        recalculate_equipment_dates(conn, eq_id)
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def update_service_record(record_id, new_date, new_tech, new_res, new_rem):
    conn = get_connection()
    try:
        rec = conn.execute(text("SELECT equipment_id, task_type FROM service_records WHERE id = :id"), {"id": record_id}).fetchone()
        if not rec: return
        eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": rec[0]}).fetchone()
        freq = eq[0] if rec[1] == "PM" else eq[1]
        next_due = str(datetime.strptime(new_date, "%Y-%m-%d").date() + relativedelta(months=int(freq)))
        conn.execute(text("UPDATE service_records SET service_date = :s_date, next_due_date = :n_due, technician = :tech, result = :res, remarks = :rem WHERE id = :id"), {"s_date": new_date, "n_due": next_due, "tech": new_tech, "res": new_res, "rem": new_rem, "id": record_id})
        recalculate_equipment_dates(conn, rec[0])
        conn.commit()
        clear_all_caches()
    finally: conn.close()

def delete_service_record(record_id):
    conn = get_connection()
    try:
        rec = conn.execute(text("SELECT equipment_id FROM service_records WHERE id = :id"), {"id": record_id}).fetchone()
        conn.execute(text("DELETE FROM service_records WHERE id = :id"), {"id": record_id})
        if rec: recalculate_equipment_dates(conn, rec[0])
        conn.commit()
        clear_all_caches()
    finally: conn.close()
