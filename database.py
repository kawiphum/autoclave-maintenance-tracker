import os
import streamlit as st
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine, text

def get_db_url():
    if "postgres" in st.secrets:
        return st.secrets["postgres"]["url"]
    return os.getenv("DATABASE_URL", "")

engine = create_engine(get_db_url(), pool_pre_ping=True)

def get_connection():
    return engine.connect()

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
    pass

def add_equipment(code, name, eq_type, brand_model, location, pm_freq, cal_freq, last_pm, last_cal):
    next_pm = calculate_next_due(last_pm, pm_freq)
    next_cal = calculate_next_due(last_cal, cal_freq)
    
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO equipments (
                equipment_code, name, type, brand_model, location, 
                pm_freq_months, cal_freq_months, last_pm_date, next_pm_date, last_cal_date, next_cal_date
            ) VALUES (:code, :name, :type, :brand, :loc, :pm_f, :cal_f, :last_pm, :next_pm, :last_cal, :next_cal)
        """), {
            "code": code, "name": name, "type": eq_type, "brand": brand_model, "loc": location,
            "pm_f": pm_freq, "cal_f": cal_freq, "last_pm": last_pm, "next_pm": next_pm,
            "last_cal": last_cal, "next_cal": next_cal
        })

def sync_equipment_latest_dates(equipment_id):
    with engine.begin() as conn:
        eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": equipment_id}).mappings().fetchone()
        if not eq:
            return

        latest_pm = conn.execute(text("""
            SELECT service_date FROM service_records 
            WHERE equipment_id = :id AND task_type = 'PM' 
            ORDER BY service_date DESC LIMIT 1
        """), {"id": equipment_id}).mappings().fetchone()
        last_pm_date = latest_pm["service_date"] if latest_pm else None
        next_pm_date = calculate_next_due(last_pm_date, eq["pm_freq_months"])

        latest_cal = conn.execute(text("""
            SELECT service_date FROM service_records 
            WHERE equipment_id = :id AND task_type = 'Calibration' 
            ORDER BY service_date DESC LIMIT 1
        """), {"id": equipment_id}).mappings().fetchone()
        last_cal_date = latest_cal["service_date"] if latest_cal else None
        next_cal_date = calculate_next_due(last_cal_date, eq["cal_freq_months"])

        conn.execute(text("""
            UPDATE equipments 
            SET last_pm_date = :last_pm, next_pm_date = :next_pm, last_cal_date = :last_cal, next_cal_date = :next_cal
            WHERE id = :id
        """), {
            "last_pm": last_pm_date, "next_pm": next_pm_date, 
            "last_cal": last_cal_date, "next_cal": next_cal_date, 
            "id": equipment_id
        })

def check_duplicate_service(equipment_id, task_type, service_date):
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT COUNT(*) AS cnt 
            FROM service_records 
            WHERE equipment_id = :id AND task_type = :task AND service_date = :s_date
        """), {"id": equipment_id, "task": task_type, "s_date": service_date}).mappings().fetchone()
        return res["cnt"] > 0

def log_service(equipment_id, task_type, service_date, technician, result, remarks):
    with engine.begin() as conn:
        row = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": equipment_id}).mappings().fetchone()
        freq = row["pm_freq_months"] if task_type == "PM" else row["cal_freq_months"]
        next_due = calculate_next_due(service_date, freq)
        
        conn.execute(text("""
            INSERT INTO service_records (equipment_id, task_type, service_date, next_due_date, technician, result, remarks)
            VALUES (:id, :task, :s_date, :next_due, :tech, :res, :rem)
        """), {
            "id": equipment_id, "task": task_type, "s_date": service_date, 
            "next_due": next_due, "tech": technician, "res": result, "rem": remarks
        })

    sync_equipment_latest_dates(equipment_id)
    return next_due

def update_service_record(record_id, service_date, technician, result, remarks):
    with engine.begin() as conn:
        rec = conn.execute(text("SELECT equipment_id, task_type FROM service_records WHERE id = :id"), {"id": record_id}).mappings().fetchone()
        if not rec:
            return
        eq_id = rec["equipment_id"]
        task_type = rec["task_type"]
        
        eq = conn.execute(text("SELECT pm_freq_months, cal_freq_months FROM equipments WHERE id = :id"), {"id": eq_id}).mappings().fetchone()
        freq = eq["pm_freq_months"] if task_type == "PM" else eq["cal_freq_months"]
        next_due = calculate_next_due(service_date, freq)
        
        conn.execute(text("""
            UPDATE service_records 
            SET service_date = :s_date, next_due_date = :next_due, technician = :tech, result = :res, remarks = :rem
            WHERE id = :id
        """), {
            "s_date": service_date, "next_due": next_due, "tech": technician,
            "res": result, "rem": remarks, "id": record_id
        })

    sync_equipment_latest_dates(eq_id)

def delete_service_record(record_id):
    with engine.begin() as conn:
        rec = conn.execute(text("SELECT equipment_id FROM service_records WHERE id = :id"), {"id": record_id}).mappings().fetchone()
        if not rec:
            return
        eq_id = rec["equipment_id"]
        conn.execute(text("DELETE FROM service_records WHERE id = :id"), {"id": record_id})

    sync_equipment_latest_dates(eq_id)

def delete_equipment(equipment_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM equipments WHERE id = :id"), {"id": equipment_id})
