import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
import database as db

# กำหนดค่าหน้าเว็บ
st.set_page_config(
    page_title="Medical Equipment PM & Calibration",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 1. Custom CSS: ฟอนต์ Prompt และดีไซน์ UI สไตล์ Dashboard สมัยใหม่
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText {
        font-family: 'Prompt', sans-serif !important;
    }

    /* ซ่อน Header และ Footer ดั้งเดิมเพื่อความคลีน */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* ตกแต่ง Metric Cards */
    .metric-container {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        flex: 1;
        padding: 1.2rem;
        border-radius: 14px;
        background: #1e222d;
        border-left: 5px solid #4a5568;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
    }
    .card-total { border-left-color: #3b82f6; }
    .card-completed { border-left-color: #10b981; }
    .card-warning { border-left-color: #f59e0b; }
    .card-overdue { border-left-color: #ef4444; }

    .metric-title {
        font-size: 0.85rem;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 0.3rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.2;
    }
    .metric-unit {
        font-size: 0.9rem;
        color: #64748b;
        font-weight: 400;
        margin-left: 0.3rem;
    }

    /* ตกแต่ง Tabs ด้านบน */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #334155;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 8px 8px 0 0;
        padding: 0 20px;
        font-size: 0.95rem;
        font-weight: 500;
        color: #94a3b8;
    }
    .stTabs [aria-selected="true"] {
        color: #38bdf8 !important;
        font-weight: 600;
        border-bottom: 3px solid #38bdf8 !important;
        background: rgba(56, 189, 248, 0.05);
    }

    /* ปรับแต่งปุ่ม Button */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# ฟังก์ชันคำนวณและประมวลผลข้อมูล
# -------------------------------------------------------------
def get_equipment_data():
    conn = db.get_connection()
    df = pd.read_sql_query(text("SELECT * FROM equipments ORDER BY id ASC"), conn)
    records_df = pd.read_sql_query(text("SELECT * FROM service_records"), conn)
    conn.close()
    return df, records_df

def calculate_status(due_date_str):
    if not due_date_str:
        return "ยังไม่มีข้อมูลรอบ", 0, "none"
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (due_date - today).days

        if days_left < 0:
            return f"เลยกำหนด {abs(days_left)} วัน", 0, "overdue"
        elif days_left <= 15:
            # คำนวณความคืบหน้านับถอยหลัง (15 วันสุดท้าย)
            progress = max(0, min(100, int((days_left / 15) * 100)))
            return f"อีก {days_left} วัน", progress, "warning"
        else:
            return f"อีก {days_left} วัน", 100, "normal"
    except Exception:
        return "รูปแบบวันที่ไม่ถูกต้อง", 0, "none"

# -------------------------------------------------------------
# Pop-up Dialogs (@st.dialog)
# -------------------------------------------------------------
@st.dialog("✏️ แก้ไขข้อมูลประวัติการตรวจเช็ค")
def edit_record_modal(record):
    with st.form("modal_edit_form"):
        new_date = st.date_input("วันที่ตรวจเช็ค", value=datetime.strptime(record["service_date"], "%Y-%m-%d").date())
        new_tech = st.text_input("ช่างผู้ตรวจ / Vendor", value=record["technician"] or "")
        
        res_list = ["Passed", "Passed with Condition", "Failed"]
        curr_idx = res_list.index(record["result"]) if record["result"] in res_list else 0
        new_res = st.selectbox("ผลการตรวจ", res_list, index=curr_idx)
        new_rem = st.text_area("หมายเหตุ", value=record["remarks"] or "")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True, type="primary"):
                db.update_service_record(record["id"], str(new_date), new_tech.strip(), new_res, new_rem.strip())
                st.success("อัปเดตเรียบร้อยแล้ว!")
                st.rerun()
        with col2:
            if st.form_submit_button("ยกเลิก", use_container_width=True):
                st.rerun()

@st.dialog("🗑️ ยืนยันการลบรายการ")
def delete_record_modal(record_id, task_title):
    st.warning(f"คุณแน่ใจหรือไม่ว่าต้องการลบรายการ **{task_title}** ออกจากฐานข้อมูลถาวร?")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("ยืนยันลบข้อมูล", type="primary", use_container_width=True):
            db.delete_service_record(record_id)
            st.success("ลบข้อมูลสำเร็จ!")
            st.rerun()
    with col2:
        if st.button("ยกเลิก", use_container_width=True):
            st.rerun()

# -------------------------------------------------------------
# Main Header
# -------------------------------------------------------------
col_header, col_date = st.columns([3, 1])
with col_header:
    st.title("🏥 ระบบติดตามรอบบำรุงรักษาเครื่องมือแพทย์")
    st.caption("Central Sterile Supply Department (CSSD) • Monitoring Dashboard")
with col_date:
    st.markdown(f"<div style='text-align: right; color: #94a3b8; padding-top: 1.5rem;'>🗓️ วันนี้: <b>{date.today().strftime('%d/%m/%Y')}</b></div>", unsafe_allow_html=True)

# โหลดข้อมูล
df_equipments, df_records = get_equipment_data()

# จัดเตรียมแท็บเมนูหลักด้านบน
tab_overview, tab_log, tab_manage, tab_history, tab_calc = st.tabs([
    "📊 ภาพรวมแดชบอร์ด",
    "📝 บันทึกผล PM/Cal",
    "⚙️ จัดการเครื่องจักร",
    "📜 ประวัติและแก้ไข",
    "🧮 คำนวณรอบล่วงหน้า"
])

# =============================================================
# TAB 1: ภาพรวมแดชบอร์ด (Overview)
# =============================================================
with tab_overview:
    if df_equipments.empty:
        st.info("💡 ยังไม่มีข้อมูลเครื่องจักรในระบบ กรุณาไปที่แท็บ 'จัดการเครื่องจักร' เพื่อเพิ่มข้อมูลเครื่องแรกครับ")
    else:
        # เตรียมคำนวณ Metrics
        total_eq = len(df_equipments)
        total_services = len(df_records)
        overdue_cnt = 0
        warning_cnt = 0

        processed_rows = []
        for _, row in df_equipments.iterrows():
            pm_status, pm_prog, pm_type = calculate_status(row["next_pm_date"])
            cal_status, cal_prog, cal_type = calculate_status(row["next_cal_date"])
            
            if pm_type == "overdue" or cal_type == "overdue":
                overdue_cnt += 1
            elif pm_type == "warning" or cal_type == "warning":
                warning_cnt += 1

            # นับจำนวนครั้งที่เคยทำจาก records
            eq_id = row["id"]
            pm_done_cnt = len(df_records[(df_records["equipment_id"] == eq_id) & (df_records["task_type"] == "PM")])
            cal_done_cnt = len(df_records[(df_records["equipment_id"] == eq_id) & (df_records["task_type"] == "Calibration")])

            processed_rows.append({
                "รหัสเครื่อง": row["equipment_code"],
                "ชื่อเครื่อง": row["name"],
                "ประเภท": row["type"],
                "จุดติดตั้ง": row["location"] or "-",
                "PM ครั้งสะสม": pm_done_cnt,
                "ต้องตรวจ PM": row["next_pm_date"] or "-",
                "นับถอยหลัง PM": pm_prog,
                "สถานะ PM": pm_status,
                "Cal ครั้งสะสม": cal_done_cnt,
                "ต้องตรวจ Cal": row["next_cal_date"] or "-",
                "นับถอยหลัง Cal": cal_prog,
                "สถานะ Cal": cal_status
            })

        view_df = pd.DataFrame(processed_rows)

        # ----------------- Modern Metric Cards -----------------
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card card-total">
                <div class="metric-title">📋 เครื่องจักรทั้งหมด</div>
                <div class="metric-value">{total_eq}<span class="metric-unit">เครื่อง</span></div>
            </div>
            <div class="metric-card card-completed">
                <div class="metric-title">✅ บันทึกตรวจสะสม</div>
                <div class="metric-value">{total_services}<span class="metric-unit">ครั้ง</span></div>
            </div>
            <div class="metric-card card-warning">
                <div class="metric-title">⚠️ ครบกำหนดใน 15 วัน</div>
                <div class="metric-value">{warning_cnt}<span class="metric-unit">เครื่อง</span></div>
            </div>
            <div class="metric-card card-overdue">
                <div class="metric-title">🚨 เลยกำหนดตรวจ (Overdue)</div>
                <div class="metric-value">{overdue_cnt}<span class="metric-unit">เครื่อง</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ตัวกรองตาราง
        f_col1, f_col2 = st.columns([2, 2])
        with f_col1:
            all_types = list(df_equipments["type"].unique())
            selected_types = st.multiselect("กรองตามประเภทเครื่อง:", options=all_types, default=all_types)
        with f_col2:
            search_text = st.text_input("🔍 ค้นหารหัส หรือชื่อเครื่อง:", placeholder="พิมพ์ค้นหา...")

        # กรองข้อมูล
        filtered_df = view_df[view_df["ประเภท"].isin(selected_types)]
        if search_text:
            filtered_df = filtered_df[
                filtered_df["รหัสเครื่อง"].str.contains(search_text, case=False, na=False) |
                filtered_df["ชื่อเครื่อง"].str.contains(search_text, case=False, na=False)
            ]

        # ----------------- ปรับแต่งตารางด้วย st.column_config -----------------
        st.dataframe(
            filtered_df,
            column_config={
                "รหัสเครื่อง": st.column_config.TextColumn("รหัส", width="small"),
                "ชื่อเครื่อง": st.column_config.TextColumn("ชื่ออุปกรณ์", width="medium"),
                "ประเภท": st.column_config.TextColumn("ประเภท", width="small"),
                "จุดติดตั้ง": st.column_config.TextColumn("ตำแหน่งที่ตั้ง", width="small"),
                "PM ครั้งสะสม": st.column_config.NumberColumn("PM (ครั้ง)", width="small"),
                "ต้องตรวจ PM": st.column_config.TextColumn("รอบถัดไป PM", width="small"),
                "นับถอยหลัง PM": st.column_config.ProgressColumn(
                    "Countdown PM",
                    help="ความคืบหน้าเข้าใกล้วันครบกำหนด (100% = ปกติ, 0% = ครบหรือเลยกำหนด)",
                    format="%d%%",
                    min_value=0,
                    max_value=100,
                    width="small"
                ),
                "สถานะ PM": st.column_config.TextColumn("สถานะ PM", width="medium"),
                "Cal ครั้งสะสม": st.column_config.NumberColumn("Cal (ครั้ง)", width="small"),
                "ต้องตรวจ Cal": st.column_config.TextColumn("รอบถัดไป Cal", width="small"),
                "นับถอยหลัง Cal": st.column_config.ProgressColumn(
                    "Countdown Cal",
                    format="%d%%",
                    min_value=0,
                    max_value=100,
                    width="small"
                ),
                "สถานะ Cal": st.column_config.TextColumn("สถานะ Cal", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )

# =============================================================
# TAB 2: บันทึกผล PM / Calibration
# =============================================================
with tab_log:
    st.subheader("📝 บันทึกประวัติการตรวจเช็คเครื่องจักร")
    if df_equipments.empty:
        st.warning("⚠️ กรุณาเพิ่มเครื่องจักรก่อนทำการบันทึกประวัติ")
    else:
        eq_options = {f"[{row['equipment_code']}] {row['name']} ({row['type']})": row['id'] for _, row in df_equipments.iterrows()}
        
        with st.form("service_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                selected_label = st.selectbox("เลือกเครื่องจักร *", list(eq_options.keys()))
                task_type = st.radio("ประเภทงาน *", ["PM", "Calibration"], horizontal=True)
                service_date = st.date_input("วันที่ตรวจเช็คจริง *", value=date.today())
            
            with col2:
                technician = st.text_input("ช่างผู้ตรวจ / Vendor *", placeholder="เช่น บ. เมดิคอล เซอร์วิส / สมชาย")
                result = st.selectbox("ผลการตรวจเช็ค *", ["Passed", "Passed with Condition", "Failed"])
                remarks = st.text_area("หมายเหตุ / อะไหล่ที่เปลี่ยน", placeholder="เช่น ล้างหม้อต้ม เปลี่ยนปะเก็นยาง...")

            submit_btn = st.form_submit_button("💾 บันทึกประวัติและคำนวณรอบถัดไปอัตโนมัติ", type="primary", use_container_width=True)

            if submit_btn:
                if not technician.strip():
                    st.error("กรุณาระบุชื่อช่างหรือผู้ตรวจเช็ค")
                else:
                    eq_id = eq_options[selected_label]
                    if db.check_duplicate_service(eq_id, task_type, str(service_date)):
                        st.warning(f"⚠️ พบประวัติการทำ {task_type} ของเครื่องนี้ในวันที่ {service_date} อยู่แล้วในระบบ")
                    else:
                        next_due = db.log_service(eq_id, task_type, str(service_date), technician.strip(), result, remarks.strip())
                        st.success(f"✅ บันทึกสำเร็จ! ระบบคำนวณวันครบกำหนดรอบถัดไปคือ: **{next_due}**")
                        st.rerun()

# =============================================================
# TAB 3: จัดการเครื่องจักร (เพิ่ม / ลบเครื่อง)
# =============================================================
with tab_manage:
    st.subheader("⚙️ เพิ่มเครื่องจักรใหม่เข้าสู่ระบบ")
    with st.expander("➕ กรอกข้อมูลเครื่องจักรใหม่", expanded=True):
        with st.form("add_eq_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                new_code = st.text_input("รหัสเครื่อง (Equipment Code) *", placeholder="เช่น ATC-01, ETO-01")
                new_name = st.text_input("ชื่อเครื่อง *", placeholder="เช่น Autoclave 300L")
                new_type = st.selectbox("ประเภทเครื่อง *", ["Autoclave", "ETO", "Plasma Sterilizer", "Washer Disinfector", "อื่นๆ"])
            with c2:
                new_brand = st.text_input("ยี่ห้อ / รุ่น", placeholder="เช่น Getinge GSS67")
                new_loc = st.text_input("จุดติดตั้ง / แผนก", placeholder="เช่น CSSD ชั้น 2")
                new_pm_freq = st.number_input("รอบ PM (ทุกๆ กี่เดือน)", min_value=1, max_value=36, value=6)
            with c3:
                new_cal_freq = st.number_input("รอบ Calibration (ทุกๆ กี่เดือน)", min_value=1, max_value=36, value=12)
                last_pm = st.date_input("ตรวจ PM ล่าสุดเมื่อ (ถ้ามี)", value=None)
                last_cal = st.date_input("ตรวจ Calibrate ล่าสุดเมื่อ (ถ้ามี)", value=None)

            if st.form_submit_button("✨ บันทึกเครื่องจักรใหม่", type="primary", use_container_width=True):
                if not new_code.strip() or not new_name.strip():
                    st.error("กรุณากรอกรหัสและชื่อเครื่องให้ครบถ้วน")
                else:
                    try:
                        db.add_equipment(
                            new_code.strip(), new_name.strip(), new_type,
                            new_brand.strip(), new_loc.strip(),
                            int(new_pm_freq), int(new_cal_freq),
                            str(last_pm) if last_pm else None,
                            str(last_cal) if last_cal else None
                        )
                        st.success(f"✅ เพิ่มเครื่องจักร '{new_name}' เข้าสู่ระบบเรียบร้อยแล้ว!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด (อาจมีรหัสเครื่องซ้ำกัน): {e}")

    # แสดงรายชื่อและปุ่มลบเครื่อง
    if not df_equipments.empty:
        st.write("---")
        st.subheader("🗑️ ลบเครื่องจักรออกจากระบบ")
        del_options = {f"[{r['equipment_code']}] {r['name']} ({r['type']})": r['id'] for _, r in df_equipments.iterrows()}
        selected_del = st.selectbox("เลือกเครื่องจักรที่ต้องการลบ:", list(del_options.keys()))
        
        if st.button("ลบเครื่องจักรที่เลือก", type="secondary"):
            db.delete_equipment(del_options[selected_del])
            st.success("ลบเครื่องจักรและประวัติที่เกี่ยวข้องเรียบร้อยแล้ว!")
            st.rerun()

# =============================================================
# TAB 4: ประวัติและแก้ไข (History & Modal Edit)
# =============================================================
with tab_history:
    st.subheader("📜 ตรวจสอบและแก้ไขประวัติการบำรุงรักษา")
    if df_equipments.empty:
        st.info("ยังไม่มีข้อมูลเครื่องจักร")
    else:
        eq_map = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        selected_history_eq = st.selectbox("เลือกเครื่องจักรที่ต้องการเรียกดูประวัติ:", list(eq_map.keys()), key="history_select")
        
        selected_id = eq_map[selected_history_eq]
        conn = db.get_connection()
        records_query = text("SELECT * FROM service_records WHERE equipment_id = :id ORDER BY service_date DESC")
        eq_records = pd.read_sql_query(records_query, conn, params={"id": selected_id})
        conn.close()

        if eq_records.empty:
            st.info("เครื่องจักรนี้ยังไม่มีประวัติการบันทึกงาน")
        else:
            st.dataframe(
                eq_records[["id", "task_type", "service_date", "next_due_date", "technician", "result", "remarks"]],
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "task_type": st.column_config.TextColumn("งาน", width="small"),
                    "service_date": st.column_config.TextColumn("วันที่ทำ", width="small"),
                    "next_due_date": st.column_config.TextColumn("รอบถัดไป", width="small"),
                    "technician": st.column_config.TextColumn("ผู้ตรวจ", width="medium"),
                    "result": st.column_config.TextColumn("ผลการตรวจ", width="small"),
                    "remarks": st.column_config.TextColumn("หมายเหตุ", width="large"),
                },
                hide_index=True,
                use_container_width=True
            )

            st.write("#### การจัดการรายการประวัติ")
            rec_options = {
                f"ID: {r['id']} | {r['task_type']} | วันที่: {r['service_date']} | ผล: {r['result']}": r 
                for _, r in eq_records.iterrows()
            }
            rec_choice = st.selectbox("เลือกรายการที่ต้องการจัดการ:", list(rec_options.keys()))
            target_record = rec_options[rec_choice]

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✏️ แก้ไขรายการนี้ (เปิด Pop-up)", use_container_width=True):
                    edit_record_modal(target_record)
            with col_btn2:
                if st.button("🗑️ ลบรายการนี้", use_container_width=True):
                    delete_record_modal(target_record["id"], f"{target_record['task_type']} วันที่ {target_record['service_date']}")

# =============================================================
# TAB 5: เครื่องมือคำนวณรอบล่วงหน้า (Due Calculator)
# =============================================================
with tab_calc:
    st.subheader("🧮 เครื่องมือคำนวณวันครบกำหนดรอบล่วงหน้า")
    st.caption("จำลองการคำนวณวันตามรอบเดือนมาตรฐานทางการแพทย์")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        base_date = st.date_input("เลือกวันที่เริ่มต้นตรวจเช็ค", value=date.today(), key="calc_base_date")
        freq_month = st.number_input("ระยะรอบความถี่ (เดือน)", min_value=1, max_value=60, value=6, step=1)
    
    with col_c2:
        calc_result = base_date + relativedelta(months=int(freq_month))
        days_diff = (calc_result - date.today()).days
        
        st.markdown(f"""
        <div style="background: #1e222d; padding: 1.5rem; border-radius: 12px; border: 1px solid #334155; margin-top: 1.2rem;">
            <div style="color: #94a3b8; font-size: 0.9rem;">ผลลัพธ์วันครบกำหนดรอบถัดไป:</div>
            <div style="font-size: 2rem; font-weight: 700; color: #38bdf8; margin: 0.5rem 0;">{calc_result.strftime('%d/%m/%Y')}</div>
            <div style="color: #64748b; font-size: 0.85rem;">(อีก {days_diff} วันนับจากวันนี้)</div>
        </div>
        """, unsafe_allow_html=True)
