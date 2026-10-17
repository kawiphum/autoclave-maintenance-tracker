import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import database as db

st.set_page_config(
    page_title="Maintenance System",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# ระบบแจ้งเตือน
# -------------------------------------------------------------
def trigger_notification(message):
    st.session_state["success_msg"] = message

# -------------------------------------------------------------
# Custom CSS: Professional Enterprise Theme
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@400;500;600&family=Sarabun:wght@300;400;500;600&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText, p, span, div, input, select, textarea, button {
        font-family: 'Sarabun', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6, .metric-value, .stTabs [data-baseweb="tab"] {
        font-family: 'Prompt', sans-serif !important;
    }

    /* จุดที่แก้ไข: เจาะจงซ่อนเฉพาะแถบด้านบนสุดของเว็บ ไม่ให้กระทบปฏิทิน */
    #MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden;}

    button[kind="primary"] {
        background-color: #059669 !important;
        color: #ffffff !important;
        border: 1px solid #059669 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.2s ease;
    }
    button[kind="primary"]:hover {
        background-color: #047857 !important;
        border-color: #047857 !important;
    }

    button[kind="secondary"] {
        background-color: #334155 !important;
        color: #f8fafc !important;
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }
    button[kind="secondary"]:hover {
        background-color: #475569 !important;
        border-color: #64748b !important;
    }

    .metric-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #334155;
    }
    .metric-title {
        font-size: 1rem;
        color: #94a3b8;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #f8fafc;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 1px solid #334155;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0;
        font-size: 1.05rem;
        color: #94a3b8;
        border: none;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #f8fafc !important;
        border-bottom: 3px solid #059669 !important;
    }

    div[data-testid="stForm"] {
        background-color: #0f172a; 
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 2rem;
    }
    
    input, textarea, div[data-baseweb="select"] > div {
        background-color: #1e293b !important; 
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
        color: #f8fafc !important;
        padding: 0.5rem !important;
    }
    input:focus, textarea:focus, div[data-baseweb="select"] > div:focus {
        border-color: #059669 !important;
        box-shadow: 0 0 0 1px #059669 !important;
    }
</style>
""", unsafe_allow_html=True)

def calculate_status(due_date_str):
    if not due_date_str:
        return "ไม่มีข้อมูล", 0, "none"
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (due_date - today).days

        if days_left < 0:
            return f"เลยกำหนด ({abs(days_left)} วัน)", 0, "overdue"
        elif days_left <= 15:
            progress = max(0, min(100, int((days_left / 15) * 100)))
            return f"ใกล้ครบกำหนด ({days_left} วัน)", progress, "warning"
        else:
            return f"ปกติ ({days_left} วัน)", 100, "normal"
    except Exception:
        return "ไม่พบข้อมูล", 0, "none"

# -------------------------------------------------------------
# Pop-up Dialogs
# -------------------------------------------------------------
@st.dialog("ตั้งค่าระบบและสาขา")
def manage_org_modal(current_hosp_name, branch_list, current_branch):
    tab_h, tab_b = st.tabs(["ตั้งชื่อระบบ", "จัดการสาขา"])
    
    with tab_h:
        with st.form("hosp_name_form"):
            new_hosp = st.text_input("ชื่อระบบหรือโรงพยาบาล", value=current_hosp_name)
            if st.form_submit_button("บันทึกการเปลี่ยนแปลง", type="primary", use_container_width=True):
                if new_hosp.strip():
                    db.update_hospital_name(new_hosp.strip())
                    trigger_notification("บันทึกชื่อระบบเรียบร้อยแล้ว")
                    st.rerun()
                else:
                    st.error("กรุณาระบุชื่อระบบ")

    with tab_b:
        with st.form("rename_branch_form"):
            st.markdown("เปลี่ยนชื่อสาขาเดิม")
            target_b = st.selectbox("เลือกสาขา", branch_list, index=branch_list.index(current_branch) if current_branch in branch_list else 0)
            new_b_name = st.text_input("ชื่อสาขาใหม่")
            if st.form_submit_button("อัปเดตชื่อสาขา", type="primary", use_container_width=True):
                if not new_b_name.strip():
                    st.error("กรุณาระบุชื่อสาขา")
                elif new_b_name.strip() == target_b:
                    st.info("ไม่มีการเปลี่ยนแปลง")
                else:
                    try:
                        db.rename_branch(target_b, new_b_name.strip())
                        st.session_state["branch_selector"] = new_b_name.strip()
                        trigger_notification("อัปเดตชื่อสาขาเรียบร้อยแล้ว")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        with st.form("add_branch_form"):
            st.markdown("เพิ่มสาขาใหม่")
            add_b_name = st.text_input("ชื่อสาขา")
            if st.form_submit_button("สร้างสาขา", use_container_width=True):
                if not add_b_name.strip():
                    st.error("กรุณาระบุชื่อสาขา")
                else:
                    try:
                        db.add_branch(add_b_name.strip())
                        st.session_state["branch_selector"] = add_b_name.strip()
                        trigger_notification("สร้างสาขาเรียบร้อยแล้ว")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        if len(branch_list) > 1:
            with st.form("del_branch_form"):
                st.markdown("ลบสาขา")
                del_b = st.selectbox("เลือกสาขาที่ต้องการลบ", branch_list)
                if st.form_submit_button("ลบสาขานี้", type="secondary", use_container_width=True):
                    try:
                        db.delete_branch(del_b)
                        trigger_notification("ลบสาขาออกจากระบบแล้ว")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

@st.dialog("แก้ไขประวัติ")
def edit_record_modal(record):
    with st.form("modal_edit_form"):
        new_date = st.date_input("วันที่ดำเนินการ", value=datetime.strptime(record["service_date"], "%Y-%m-%d").date())
        new_tech = st.text_input("ผู้ดำเนินการ", value=record["technician"] or "")
        
        res_list = ["Passed", "Passed with Condition", "Failed"]
        curr_idx = res_list.index(record["result"]) if record["result"] in res_list else 0
        new_res = st.selectbox("ผลการตรวจสอบ", res_list, index=curr_idx)
        new_rem = st.text_area("หมายเหตุ", value=record["remarks"] or "")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.form_submit_button("บันทึกการแก้ไข", use_container_width=True, type="primary"):
                db.update_service_record(int(record["id"]), str(new_date), new_tech.strip(), new_res, new_rem.strip())
                trigger_notification("แก้ไขประวัติเรียบร้อยแล้ว")
                st.rerun()
        with col2:
            if st.form_submit_button("ยกเลิก", use_container_width=True):
                st.rerun()

@st.dialog("ยืนยันการลบ")
def delete_record_modal(record_id, task_title):
    st.write(f"ต้องการลบรายการ {task_title} ใช่หรือไม่?")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("ยืนยันการลบ", type="primary", use_container_width=True):
            db.delete_service_record(int(record_id))
            trigger_notification("ลบข้อมูลสำเร็จ")
            st.rerun()
    with col2:
        if st.button("ยกเลิก", use_container_width=True):
            st.rerun()

# -------------------------------------------------------------
# โหลดข้อมูล และจัด Layout Header ให้เรียบร้อย
# -------------------------------------------------------------
hospital_name = db.get_hospital_name()
BRANCH_LIST = db.get_branches()

st.markdown(f"<h1 style='font-size: 1.8rem; margin-bottom: 0.5rem;'>{hospital_name}</h1>", unsafe_allow_html=True)

col_h1, col_h2, col_h3 = st.columns([3, 2, 5])
with col_h1:
    selected_branch = st.selectbox("พื้นที่ปฏิบัติงาน", options=BRANCH_LIST, key="branch_selector")
with col_h2:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    if st.button("ตั้งค่าระบบ", use_container_width=True):
        manage_org_modal(hospital_name, BRANCH_LIST, selected_branch)

# จองพื้นที่คงที่สำหรับกล่องแจ้งเตือน (ป้องกันโครงสร้างเว็บขยับจนแท็บรีเซ็ต)
noti_container = st.container()
with noti_container:
    if "success_msg" in st.session_state:
        st.success(st.session_state["success_msg"])
        del st.session_state["success_msg"]
    else:
        # ใส่กล่องล่องหนไว้จองพื้นที่ตอนที่ไม่มีข้อความ
        st.markdown("<div style='height: 0px;'></div>", unsafe_allow_html=True)

df_equipments, df_records = db.get_branch_data_cached(selected_branch)

tab_overview, tab_manage, tab_log, tab_history, tab_calc = st.tabs([
    "ภาพรวมระบบ",
    "ทะเบียนเครื่องจักร", 
    "บันทึกผลตรวจสอบ",
    "ประวัติข้อมูล",
    "คำนวณรอบ"
])

# =============================================================
# TAB 1: ภาพรวมระบบ
# =============================================================
with tab_overview:
    total_eq = len(df_equipments)
    total_services = len(df_records)
    overdue_cnt = 0
    warning_cnt = 0
    processed_rows = []

    if not df_equipments.empty:
        for _, row in df_equipments.iterrows():
            pm_status, pm_prog, pm_type = calculate_status(row["next_pm_date"])
            cal_status, cal_prog, cal_type = calculate_status(row["next_cal_date"])
            
            if pm_type == "overdue" or cal_type == "overdue":
                overdue_cnt += 1
            elif pm_type == "warning" or cal_type == "warning":
                warning_cnt += 1

            eq_id = row["id"]
            pm_done_cnt = len(df_records[(df_records["equipment_id"] == eq_id) & (df_records["task_type"] == "PM")]) if not df_records.empty else 0
            cal_done_cnt = len(df_records[(df_records["equipment_id"] == eq_id) & (df_records["task_type"] == "Calibration")]) if not df_records.empty else 0

            processed_rows.append({
                "รหัส": row["equipment_code"],
                "ชื่ออุปกรณ์": row["name"],
                "ประเภท": row["type"],
                "แผนก": row["location"] or "-",
                "PM (รอบถัดไป)": row["next_pm_date"] or "-",
                "สถานะ PM": pm_status,
                "Cal (รอบถัดไป)": row["next_cal_date"] or "-",
                "สถานะ Cal": cal_status
            })

    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card card-success">
            <div class="metric-title">เครื่องจักรทั้งหมด</div>
            <div class="metric-value">{total_eq}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">ประวัติการตรวจสอบ</div>
            <div class="metric-value">{total_services}</div>
        </div>
        <div class="metric-card card-warning">
            <div class="metric-title" style="color:#F59E0B;">ใกล้ครบกำหนด</div>
            <div class="metric-value">{warning_cnt}</div>
        </div>
        <div class="metric-card card-danger">
            <div class="metric-title" style="color:#EF4444;">เลยกำหนด</div>
            <div class="metric-value">{overdue_cnt}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df_equipments.empty:
        st.info("ไม่มีข้อมูลในระบบ")
    else:
        view_df = pd.DataFrame(processed_rows)
        c1, c2 = st.columns([1, 1])
        with c1:
            all_types = list(df_equipments["type"].unique())
            selected_types = st.multiselect("กรองตามประเภท:", options=all_types, default=all_types)
        with c2:
            search_text = st.text_input("ค้นหาจากรหัสหรือชื่ออุปกรณ์:")

        filtered_df = view_df[view_df["ประเภท"].isin(selected_types)]
        if search_text:
            filtered_df = filtered_df[
                filtered_df["รหัส"].str.contains(search_text, case=False, na=False) |
                filtered_df["ชื่ออุปกรณ์"].str.contains(search_text, case=False, na=False)
            ]

        st.dataframe(filtered_df, hide_index=True, use_container_width=True)

# =============================================================
# TAB 2: ทะเบียนเครื่องจักร
# =============================================================
with tab_manage:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1rem;'>ลงทะเบียนเครื่องจักรใหม่</h3>", unsafe_allow_html=True)
    
    default_types = ["Autoclave", "ETO", "Plasma Sterilizer", "Washer Disinfector"]
    existing_types = [t for t in df_equipments["type"].unique() if t not in default_types] if not df_equipments.empty else []
    all_type_options = default_types + existing_types + ["ระบุประเภทอื่น..."]

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        selected_type = st.selectbox("ประเภทเครื่อง", options=all_type_options)
    
    if selected_type == "ระบุประเภทอื่น...":
        with col_t2:
            custom_type = st.text_input("พิมพ์ชื่อประเภทเครื่องใหม่")
    else:
        custom_type = selected_type

    with st.form("add_equipment_form", clear_on_submit=True):
        st.markdown("<p style='font-weight:600; margin-bottom:1rem; color:#94A3B8;'>รายละเอียดเครื่องจักร</p>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            new_code = st.text_input("รหัสอุปกรณ์ *")
            new_name = st.text_input("ชื่ออุปกรณ์ *")
        with c2:
            new_brand = st.text_input("ยี่ห้อ / รุ่น")
            new_loc = st.text_input("แผนก / จุดติดตั้ง")
            new_pm_freq = st.number_input("รอบ PM (เดือน)", min_value=1, value=6)
        with c3:
            new_cal_freq = st.number_input("รอบ Calibration (เดือน)", min_value=1, value=12)
            last_pm = st.date_input("วันที่ PM ล่าสุด (ถ้ามี)", value=None)
            last_cal = st.date_input("วันที่ Calibrate ล่าสุด (ถ้ามี)", value=None)

        st.markdown("<br>", unsafe_allow_html=True)
    if st.form_submit_button("บันทึกข้อมูลเครื่องจักร", type="primary"):
            final_type = custom_type.strip()
            if not new_code.strip() or not new_name.strip() or not final_type:
                st.error("กรุณากรอกข้อมูลบังคับ (*) ให้ครบถ้วน")
            else:
                # 🛑 เพิ่ม Spinner ตรงนี้
                with st.spinner("⏳ กำลังบันทึกข้อมูลลงระบบ กรุณารอสักครู่..."):
                    try:
                        db.add_equipment(
                            new_code.strip(), new_name.strip(), final_type,
                            new_brand.strip(), new_loc.strip(),
                            int(new_pm_freq), int(new_cal_freq),
                            str(last_pm) if last_pm else None,
                            str(last_cal) if last_cal else None,
                            branch=selected_branch
                        )
                        trigger_notification("ลงทะเบียนเครื่องจักรเรียบร้อยแล้ว")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    if not df_equipments.empty:
        st.markdown("<br><h3 style='font-size:1.2rem; margin-bottom:1rem;'>ลบข้อมูลเครื่องจักร</h3>", unsafe_allow_html=True)
        del_options = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1:
            selected_del = st.selectbox("เลือกอุปกรณ์", list(del_options.keys()), label_visibility="collapsed")
        with c_del2:
            if st.button("ลบข้อมูล", type="secondary", use_container_width=True):
                db.delete_equipment(int(del_options[selected_del]))
                trigger_notification("ลบข้อมูลเครื่องจักรสำเร็จ")
                st.rerun()

# =============================================================
# TAB 3: บันทึกผล PM / Calibration
# =============================================================
with tab_log:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1rem;'>บันทึกประวัติการตรวจสอบ</h3>", unsafe_allow_html=True)
    if df_equipments.empty:
        st.info("ไม่พบข้อมูลเครื่องจักรในสาขานี้")
    else:
        eq_options = {f"[{row['equipment_code']}] {row['name']}": row['id'] for _, row in df_equipments.iterrows()}
        
        with st.form("service_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                selected_label = st.selectbox("อุปกรณ์ *", list(eq_options.keys()))
                task_type = st.radio("ประเภทงาน *", ["PM", "Calibration"], horizontal=True)
                service_date = st.date_input("วันที่ดำเนินการ *", value=date.today())
            
            with col2:
                technician = st.text_input("ผู้ดำเนินการ *")
                result = st.selectbox("ผลการตรวจสอบ *", ["Passed", "Passed with Condition", "Failed"])
                remarks = st.text_area("หมายเหตุ")

            st.markdown("<br>", unsafe_allow_html=True)
           if st.form_submit_button("บันทึกประวัติ", type="primary"):
                if not technician.strip():
                    st.error("กรุณาระบุผู้ดำเนินการ")
                else:
                    # 🛑 เพิ่ม Spinner ตรงนี้
                    with st.spinner("⏳ กำลังบันทึกประวัติและคำนวณรอบถัดไป..."):
                        eq_id = int(eq_options[selected_label])
                        if db.check_duplicate_service(eq_id, task_type, str(service_date)):
                            st.warning("มีประวัติในระบบแล้ว")
                        else:
                            db.log_service(eq_id, task_type, str(service_date), technician.strip(), result, remarks.strip())
                            trigger_notification("บันทึกประวัติและคำนวณรอบถัดไปสำเร็จ")
                            st.rerun()

# =============================================================
# TAB 4: ประวัติและแก้ไข
# =============================================================
with tab_history:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1rem;'>ค้นหาและแก้ไขประวัติ</h3>", unsafe_allow_html=True)
    if df_equipments.empty:
        st.info("ไม่พบข้อมูล")
    else:
        eq_map = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        selected_history_eq = st.selectbox("ค้นหาประวัติอุปกรณ์", list(eq_map.keys()), label_visibility="collapsed")
        
        selected_id = int(eq_map[selected_history_eq])
        eq_records = df_records[df_records["equipment_id"] == selected_id] if not df_records.empty else pd.DataFrame()

        if eq_records.empty:
            st.info("ไม่มีประวัติการดำเนินการ")
        else:
            # --- ส่วนที่เพิ่มใหม่: คำนวณและแสดงยอดรวมสะสม ---
            total_pm = len(eq_records[eq_records["task_type"] == "PM"])
            total_cal = len(eq_records[eq_records["task_type"] == "Calibration"])

            st.markdown(f"""
            <div style='display: flex; gap: 1rem; margin-bottom: 1.2rem;'>
                <div style='background-color: #1e293b; padding: 0.8rem 1.2rem; border-radius: 6px; border: 1px solid #334155; width: 50%;'>
                    <div style='color: #94A3B8; font-size: 0.9rem;'>ยอดรวม PM สะสม</div>
                    <div style='color: #10B981; font-size: 1.5rem; font-weight: 600;'>{total_pm} <span style='font-size: 0.9rem; font-weight: 400; color: #94A3B8;'>ครั้ง</span></div>
                </div>
                <div style='background-color: #1e293b; padding: 0.8rem 1.2rem; border-radius: 6px; border: 1px solid #334155; width: 50%;'>
                    <div style='color: #94A3B8; font-size: 0.9rem;'>ยอดรวม Calibration สะสม</div>
                    <div style='color: #3B82F6; font-size: 1.5rem; font-weight: 600;'>{total_cal} <span style='font-size: 0.9rem; font-weight: 400; color: #94A3B8;'>ครั้ง</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            # ------------------------------------------------

            # 1. คัดลอกข้อมูล
            display_records = eq_records.copy()
            
            # 2. จัดเรียงเอาวันที่ทำล่าสุดขึ้นก่อน
            display_records = display_records.sort_values(by=["service_date", "id"], ascending=[False, False]).reset_index(drop=True)
            
            # 3. รันเลข "ลำดับ" 1, 2, 3... จากบนลงล่าง
            display_records.insert(0, 'ลำดับ', range(1, len(display_records) + 1))
            
            # 4. นำไปแสดงผล
            st.dataframe(
                display_records[["ลำดับ", "task_type", "service_date", "technician", "result", "remarks"]],
                hide_index=True,
                use_container_width=True
            )

            st.markdown("<br><p style='font-size:1rem; color:#94A3B8; margin-bottom:0.5rem;'>จัดการข้อมูลประวัติ</p>", unsafe_allow_html=True)
            rec_options = {f"{r['service_date']} | {r['task_type']} | {r['result']}": r for _, r in eq_records.iterrows()}
            c_rec1, c_rec2, c_rec3 = st.columns([2, 1, 1])
            with c_rec1:
                rec_choice = st.selectbox("เลือกรายการ", list(rec_options.keys()), label_visibility="collapsed")
                target_record = rec_options[rec_choice]
            with c_rec2:
                if st.button("แก้ไขรายการ", type="primary", use_container_width=True):
                    edit_record_modal(target_record)
            with c_rec3:
                if st.button("ลบรายการ", type="secondary", use_container_width=True):
                    delete_record_modal(target_record["id"], f"{target_record['task_type']}")

# =============================================================
# TAB 5: คำนวณรอบล่วงหน้า
# =============================================================
with tab_calc:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1.5rem;'>ระบบจำลองการคำนวณรอบ</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        base_date = st.date_input("วันที่เริ่มต้น")
        freq_month = st.number_input("ความถี่ (เดือน)", min_value=1, value=6)
    with c2:
        calc_result = base_date + relativedelta(months=int(freq_month))
        st.markdown(f"""
        <div style="background-color: #1E293B; padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; margin-top: 1.7rem;">
            <div style="color: #94A3B8; font-size: 1rem;">วันที่ครบกำหนดรอบถัดไป</div>
            <div style="font-size: 2.2rem; font-weight: 600; color: #10B981;">{calc_result.strftime('%d/%m/%Y')}</div>
        </div>
        """, unsafe_allow_html=True)
