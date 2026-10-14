from sqlalchemy import text
import streamlit as st
import pandas as pd
from datetime import datetime, date
import database as db

st.set_page_config(page_title="Autoclave & ETO Maintenance Tracker", layout="wide")
db.init_db()

# --- ฟังก์ชันคำนวณระยะเวลาคงเหลือ / นับถอยหลัง ---
def get_countdown_info(next_date_str):
    if pd.isna(next_date_str) or not isinstance(next_date_str, str) or not next_date_str.strip():
        return "ยังไม่มีข้อมูลรอบ"
    
    try:
        target_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (target_date - today).days
        
        if days_left < 0:
            return f"🚨 เลยกำหนดแล้ว {abs(days_left)} วัน"
        elif days_left == 0:
            return "⚠️ ครบกำหนดวันนี้!"
        elif days_left <= 15:
            return f"⚠️ อีก {days_left} วัน (ด่วน)"
        elif days_left <= 30:
            return f"⏳ อีก {days_left} วัน"
        else:
            return f"✅ อีก {days_left} วัน"
    except Exception:
        return "รูปแบบวันที่ไม่ถูกต้อง"

# --- เมนูหลัก ---
menu = st.sidebar.selectbox("เลือกฟังก์ชัน", [
    "แดชบอร์ดตรวจเช็ครอบ (Dashboard)", 
    "บันทึกประวัติ PM / Calibrate", 
    "จัดการ/แก้ไขประวัติ (Edit/Delete)",
    "เครื่องมือคำนวณรอบถัดไป (Due Calculator)",
    "จัดการเครื่องจักร (เพิ่ม/ลบเครื่อง)"
])

# ==========================================
# 1. แดชบอร์ด (DASHBOARD)
# ==========================================
if menu == "แดชบอร์ดตรวจเช็ครอบ (Dashboard)":
    st.title("🏥 แดชบอร์ดติดตามรอบ PM & Calibration (Autoclave / ETO)")
    st.caption(f"ข้อมูล ณ วันที่ {date.today().strftime('%d/%m/%Y')}")
    
    conn = db.get_connection()
    query = """
        SELECT 
            e.*,
            COALESCE(pm_agg.pm_count, 0) AS pm_times,
            COALESCE(cal_agg.cal_count, 0) AS cal_times,
            (COALESCE(pm_agg.pm_count, 0) + COALESCE(cal_agg.cal_count, 0)) AS total_service_times
        FROM equipments e
        LEFT JOIN (
            SELECT equipment_id, COUNT(*) AS pm_count 
            FROM service_records 
            WHERE task_type = 'PM' 
            GROUP BY equipment_id
        ) pm_agg ON e.id = pm_agg.equipment_id
        LEFT JOIN (
            SELECT equipment_id, COUNT(*) AS cal_count 
            FROM service_records 
            WHERE task_type = 'Calibration' 
            GROUP BY equipment_id
        ) cal_agg ON e.id = cal_agg.equipment_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        st.info("ยังไม่มีข้อมูลเครื่องจักร กรุณาไปที่เมนู 'จัดการเครื่องจักร (เพิ่ม/ลบเครื่อง)'")
    else:
        df["PM_Countdown"] = df["next_pm_date"].apply(get_countdown_info)
        df["Cal_Countdown"] = df["next_cal_date"].apply(get_countdown_info)
        
        overdue_total = sum(df["PM_Countdown"].str.contains("เลยกำหนด") | df["Cal_Countdown"].str.contains("เลยกำหนด"))
        due_soon_total = sum(df["PM_Countdown"].str.contains("ด่วน") | df["Cal_Countdown"].str.contains("ด่วน"))
        total_all_services = df["total_service_times"].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("จำนวนเครื่องทั้งหมด", f"{len(df)} เครื่อง")
        col2.metric("ตรวจเช็คสะสมทั้งหมด", f"{total_all_services} ครั้ง")
        col3.metric("🚨 เลยกำหนด (Overdue)", f"{overdue_total} รายการ")
        col4.metric("⚠️ ครบกำหนดใน 15 วัน", f"{due_soon_total} รายการ")
        
        st.divider()
        
        c1, c2 = st.columns(2)
        type_filter = c1.multiselect("กรองตามประเภทเครื่อง", options=df["type"].unique(), default=df["type"].unique())
        search = c2.text_input("ค้นหาตามรหัส หรือ ชื่อเครื่อง")
        
        view_df = df[df["type"].isin(type_filter)]
        if search:
            view_df = view_df[view_df["equipment_code"].str.contains(search, case=False) | view_df["name"].str.contains(search, case=False)]
            
        table_cols = [
            "equipment_code", "name", "type", "location",
            "pm_times", "last_pm_date", "next_pm_date", "PM_Countdown",
            "cal_times", "last_cal_date", "next_cal_date", "Cal_Countdown",
            "total_service_times"
        ]
        
        st.subheader("📋 สถานะรอบตรวจและจำนวนครั้งที่ตรวจสะสม")
        st.dataframe(
            view_df[table_cols].rename(columns={
                "equipment_code": "รหัสเครื่อง", "name": "ชื่อเครื่อง", "type": "ประเภท",
                "location": "จุดติดตั้ง", "pm_times": "ทำ PM แล้ว (ครั้ง)", "last_pm_date": "PM ล่าสุด",
                "next_pm_date": "ต้องตรวจ PM อีกที", "PM_Countdown": "นับถอยหลัง PM",
                "cal_times": "Cal แล้ว (ครั้ง)", "last_cal_date": "Cal ล่าสุด",
                "next_cal_date": "ต้อง Cal อีกที", "Cal_Countdown": "นับถอยหลัง Cal",
                "total_service_times": "รวมตรวจแล้ว (ครั้ง)"
            }),
            use_container_width=True,
            hide_index=True
        )

# ==========================================
# 2. บันทึกผลงาน (LOG SERVICE) พร้อม VALIDATION ห้ามซ้ำ
# ==========================================
elif menu == "บันทึกประวัติ PM / Calibrate":
    st.header("📝 บันทึกผลการตรวจเช็ค PM / Calibration")
    
    conn = db.get_connection()
    equipments = pd.read_sql_query("SELECT id, equipment_code, name, type, pm_freq_months, cal_freq_months FROM equipments", conn)
    conn.close()
    
    if equipments.empty:
        st.warning("ยังไม่มีข้อมูลเครื่องจักร กรุณาเพิ่มเครื่องจักรก่อน")
    else:
        eq_map = {f"[{row['equipment_code']}] {row['name']} ({row['type']})": row for _, row in equipments.iterrows()}
        selected_label = st.selectbox("เลือกเครื่องจักร", options=list(eq_map.keys()))
        selected_row = eq_map[selected_label]
        
        with st.form("service_form"):
            task_type = st.radio("ประเภทงานที่ทำ", ["PM", "Calibration"], horizontal=True)
            service_date = st.date_input("วันที่ตรวจเช็คล่าสุด (เสร็จสิ้น)", value=date.today())
            
            current_freq = selected_row["pm_freq_months"] if task_type == "PM" else selected_row["cal_freq_months"]
            st.info(f"💡 เครื่องนี้ตั้งรอบความถี่ไว้ที่: **ทุกๆ {current_freq} เดือน**")
            
            technician = st.text_input("ช่างผู้ตรวจ / บริษัท Vendor ผู้สอบเทียบ *")
            result = st.selectbox("ผลการตรวจ", ["Passed", "Passed with Condition", "Failed"])
            remarks = st.text_area("หมายเหตุ / ผลการทดสอบ Chamber / ค่า Error")
            
            submit = st.form_submit_button("บันทึกผลงาน")
            if submit:
                # 1. เช็คว่ากรอกชื่อช่างหรือยัง
                if not technician.strip():
                    st.error("❌ กรุณากรอก 'ช่างผู้ตรวจ / บริษัท Vendor ผู้สอบเทียบ' ก่อนบันทึก")
                
                # 2. เช็คว่าเคยมีบันทึกของเครื่องนี้ ในงานประเภทนี้ วันที่นี้ ไปแล้วหรือยัง
                elif db.check_duplicate_service(selected_row["id"], task_type, str(service_date)):
                    st.error(f"⚠️ รายการซ้ำ! เครื่องนี้มีการบันทึกงาน **{task_type}** ของวันที่ **{service_date}** ไปแล้ว หากต้องการแก้ไข ให้ไปที่เมนู 'จัดการ/แก้ไขประวัติ (Edit/Delete)'")
                
                # 3. บันทึกเมื่อข้อมูลถูกต้องและไม่ซ้ำ
                else:
                    next_date = db.log_service(selected_row["id"], task_type, str(service_date), technician.strip(), result, remarks.strip())
                    st.success(f"บันทึกสำเร็จ! วันที่ต้องตรวจ {task_type} ครั้งถัดไปคือ: **{next_date}**")

# ==========================================
# 3. จัดการ/แก้ไขประวัติ (Edit/Delete)
# ==========================================
elif menu == "จัดการ/แก้ไขประวัติ (Edit/Delete)":
    st.header("🛠️ จัดการ แก้ไข หรือลบประวัติการตรวจเช็ค")
    
    conn = db.get_connection()
    equipments = pd.read_sql_query(text("SELECT id, equipment_code, name, type FROM equipments"), conn)
    
    if equipments.empty:
        st.warning("⚠️ ยังไม่มีข้อมูลเครื่องจักรในระบบ กรุณาเพิ่มเครื่องจักรก่อน")
        conn.close()
    else:
        eq_map = {f"[{row['equipment_code']}] {row['name']}": row for _, row in equipments.iterrows()}
        selected_label = st.selectbox("เลือกเครื่องจักรที่ต้องการดูประวัติ", options=list(eq_map.keys()))
        selected_eq = eq_map[selected_label]
        eq_id = int(selected_eq["id"])
        
        # ดึงประวัติการตรวจเช็คของเครื่องที่เลือก (รองรับ PostgreSQL / Supabase)
        records_query = text("SELECT * FROM service_records WHERE equipment_id = :eq_id ORDER BY service_date DESC")
        records = pd.read_sql_query(records_query, conn, params={"eq_id": eq_id})
        conn.close()
        
        if records.empty:
            st.info("เครื่องจักรนี้ยังไม่มีประวัติการตรวจเช็ค PM หรือ Calibration")
        else:
            st.subheader("📋 ประวัติการตรวจเช็คที่ผ่านมา")
            st.dataframe(
                records[["id", "task_type", "service_date", "next_due_date", "technician", "result", "remarks"]], 
                use_container_width=True
            )
            
            record_options = {
                f"ID {r['id']} | งาน: {r['task_type']} | วันที่: {r['service_date']} | ผล: {r['result']}": r 
                for _, r in records.iterrows()
            }
            selected_rec_label = st.selectbox("เลือกรายการที่ต้องการแก้ไข หรือลบ", list(record_options.keys()))
            selected_rec = record_options[selected_rec_label]
            
            col_edit, col_del = st.columns(2)
            
            # --- ส่วนแก้ไข ---
            with col_edit:
                with st.expander("✏️ แก้ไขข้อมูลรายการนี้"):
                    with st.form("edit_rec_form"):
                        new_date = st.date_input("วันที่ตรวจเช็ค", value=datetime.strptime(selected_rec["service_date"], "%Y-%m-%d").date())
                        new_tech = st.text_input("ช่างผู้ตรวจ / Vendor", value=selected_rec["technician"] or "")
                        
                        res_list = ["Passed", "Passed with Condition", "Failed"]
                        res_idx = res_list.index(selected_rec["result"]) if selected_rec["result"] in res_list else 0
                        new_res = st.selectbox("ผลการตรวจ", res_list, index=res_idx)
                        new_rem = st.text_area("หมายเหตุ", value=selected_rec["remarks"] or "")
                        
                        if st.form_submit_button("บันทึกการแก้ไข"):
                            db.update_service_record(selected_rec["id"], str(new_date), new_tech.strip(), new_res, new_rem.strip())
                            st.success("✅ อัปเดตข้อมูลเรียบร้อยแล้ว!")
                            st.rerun()
                            
            # --- ส่วนลบ ---
            with col_del:
                with st.expander("🗑️ ลบรายการนี้ออกจากระบบ"):
                    st.warning(f"ต้องการลบรายการ {selected_rec['task_type']} วันที่ {selected_rec['service_date']} ใช่หรือไม่?")
                    if st.button("ยืนยันการลบรายการ", type="primary"):
                        db.delete_service_record(selected_rec["id"])
                        st.success("✅ ลบรายการเรียบร้อยแล้ว!")
                        st.rerun()

# ==========================================
# 4. เครื่องมือคำนวณรอบถัดไป (DUE CALCULATOR)
# ==========================================
elif menu == "เครื่องมือคำนวณรอบถัดไป (Due Calculator)":
    st.header("🧮 เครื่องมือจำลองและคำนวณรอบการตรวจครั้งถัดไป")
    c1, c2 = st.columns(2)
    test_date = c1.date_input("ใส่วันที่ตรวจเช็คล่าสุด", value=date.today())
    test_months = c2.number_input("รอบความถี่ (จำนวนเดือน)", min_value=1, max_value=60, value=6, step=1)
    
    calc_next = db.calculate_next_due(str(test_date), test_months)
    countdown_text = get_countdown_info(calc_next)
    
    st.success(f"""
    ### ผลการคำนวณ:
    - **วันที่ทำล่าสุด:** {test_date.strftime('%d/%m/%Y')}
    - **รอบความถี่:** ทุก {test_months} เดือน
    - **📅 ต้องตรวจเช็คอีกครั้งในวันที่:** **{calc_next}**
    - **สถานะ:** {countdown_text}
    """)

# ==========================================
# 5. จัดการเครื่องจักร (เพิ่ม / ลบเครื่อง)
# ==========================================
elif menu == "จัดการเครื่องจักร (เพิ่ม/ลบเครื่อง)":
    st.header("⚙️ จัดการข้อมูลเครื่องจักร (Autoclave / ETO)")
    
    tab_add, tab_delete = st.tabs(["➕ เพิ่มเครื่องจักรใหม่", "🗑️ ลบเครื่องจักรออกจากระบบ"])
    
    # --- TAB 1: เพิ่มเครื่องจักรใหม่ ---
    with tab_add:
        st.subheader("เพิ่มข้อมูลเครื่องจักรใหม่")
        st.caption("หมายเหตุ: ช่องที่มีเครื่องหมาย * จำเป็นต้องระบุให้ครบถ้วน")
        
        # แสดงกล่องข้อความสีเขียวแจ้งเตือนหากเพิ่งบันทึกสำเร็จ
        if "add_success_msg" in st.session_state:
            st.success(st.session_state["add_success_msg"])
            del st.session_state["add_success_msg"]  # เคลียร์ค่าออกหลังจากแสดงแล้ว

        # ดึงประเภทเครื่องเดิมที่มีอยู่ในระบบมาแสดงเป็นตัวเลือก
        conn = db.get_connection()
        existing_types = pd.read_sql_query("SELECT DISTINCT type FROM equipments", conn)["type"].dropna().tolist()
        conn.close()
        
        default_types = ["Autoclave", "ETO"]
        all_types = sorted(list(set(default_types + existing_types)))
        type_options = all_types + ["➕ เพิ่มประเภทอื่น ๆ (ระบุเอง)"]
        
        selected_type_option = st.selectbox("ประเภทเครื่อง *", type_options)
        
        custom_type = ""
        if selected_type_option == "➕ เพิ่มประเภทอื่น ๆ (ระบุเอง)":
            custom_type = st.text_input("ระบุชื่อประเภทเครื่องใหม่ *", placeholder="เช่น Plasma Sterilizer, Washer Disinfector")

        with st.form("add_eq_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            code = col1.text_input("รหัสเครื่อง (Equipment Code) *", placeholder="เช่น ATC-01, ETO-01")
            name = col2.text_input("ชื่อเครื่อง *", placeholder="เช่น Steam Sterilizer 300L")
            brand_model = col1.text_input("ยี่ห้อ / รุ่น *", placeholder="เช่น Getinge / HS66")
            location = col2.text_input("สถานที่ติดตั้ง / แผนก *", placeholder="เช่น แผนกจ่ายกลาง (CSSD) ชั้น 2")
            
            st.subheader("กำหนดรอบความถี่มาตรฐาน (เดือน)")
            col3, col4 = st.columns(2)
            pm_freq = col3.number_input("รอบตรวจ PM (เดือน)", min_value=1, value=6)
            cal_freq = col4.number_input("รอบสอบเทียบ Calibration (เดือน)", min_value=1, value=12)
            
            st.subheader("ประวัติครั้งล่าสุด (ถ้ามี)")
            col5, col6 = st.columns(2)
            last_pm = col5.date_input("วันที่ทำ PM ล่าสุด", value=None)
            last_cal = col6.date_input("วันที่ Calibrate ล่าสุด", value=None)
            
            submit = st.form_submit_button("บันทึกเครื่องจักร")
            if submit:
                final_type = custom_type.strip() if selected_type_option == "➕ เพิ่มประเภทอื่น ๆ (ระบุเอง)" else selected_type_option.strip()

                missing_fields = []
                if not code.strip():
                    missing_fields.append("รหัสเครื่อง")
                if not name.strip():
                    missing_fields.append("ชื่อเครื่อง")
                if not final_type:
                    missing_fields.append("ประเภทเครื่อง (ต้องระบุชื่อประเภท)")
                if not brand_model.strip():
                    missing_fields.append("ยี่ห้อ / รุ่น")
                if not location.strip():
                    missing_fields.append("สถานที่ติดตั้ง")
                    
                if missing_fields:
                    st.error(f"❌ กรุณากรอกข้อมูลให้ครบถ้วน ขาดรายการ: {', '.join(missing_fields)}")
                else:
                    try:
                        db.add_equipment(
                            code.strip(), name.strip(), final_type, brand_model.strip(), location.strip(), pm_freq, cal_freq,
                            str(last_pm) if last_pm else None,
                            str(last_cal) if last_cal else None
                        )
                        # ฝากข้อความสีเขียวไว้ใน session_state เพื่อแสดงหลังรีเฟรชหน้า
                        st.session_state["add_success_msg"] = f"✅ บันทึกสำเร็จ! เพิ่มเครื่อง [{code.strip()}] {name.strip()} เข้าสู่ระบบเรียบร้อยแล้ว"
                        st.toast(f"บันทึกเครื่อง {code.strip()} สำเร็จ!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด (อาจมีรหัสเครื่องซ้ำในระบบ): {e}")

    # --- TAB 2: ลบเครื่องจักรออกจากระบบ ---
    with tab_delete:
        st.subheader("ลบเครื่องจักรที่ไม่ใช้งาน")
        
        conn = db.get_connection()
        eq_df = pd.read_sql_query("SELECT id, equipment_code, name, type, location FROM equipments", conn)
        conn.close()
        
        if eq_df.empty:
            st.info("ไม่มีเครื่องจักรในระบบให้ลบ")
        else:
            eq_del_options = {f"[{row['equipment_code']}] {row['name']} ({row['type']}) - {row['location']}": row["id"] for _, row in eq_df.iterrows()}
            selected_del_label = st.selectbox("เลือกเครื่องจักรที่ต้องการลบ", options=list(eq_del_options.keys()))
            selected_del_id = eq_del_options[selected_del_label]
            
            st.error("⚠️ คำเตือน: การลบเครื่องจักรจะลบข้อมูลประวัติการตรวจเช็ค PM และ Calibration ของเครื่องนี้ทั้งหมดอย่างถาวร")
            confirm_del = st.checkbox("ฉันเข้าใจและยืนยันว่าต้องการลบเครื่องนี้ออกจากระบบ")
            
            if st.button("🗑️ ยืนยันการลบเครื่องจักร", type="primary", disabled=not confirm_del):
                db.delete_equipment(selected_del_id)
                st.success(f"ลบเครื่อง {selected_del_label} และประวัติที่เกี่ยวข้องเรียบร้อยแล้ว!")
                st.rerun()
