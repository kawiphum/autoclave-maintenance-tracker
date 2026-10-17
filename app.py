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
# Custom CSS: Minimalist Enterprise Dark Theme (สไตล์ Supabase)
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Prompt:wght@300;400;500;600&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText {
        font-family: 'Prompt', 'Inter', sans-serif !important;
    }

    #MainMenu, footer, header {visibility: hidden;}

    /* สีปุ่มหลัก (Primary Button) */
    .stButton>button[kind="primary"] {
        background-color: #24b47e !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #1e986a !important;
    }

    /* ปุ่มรอง (Secondary Button) */
    .stButton>button[kind="secondary"] {
        background-color: transparent !important;
        color: #ededed !important;
        border: 1px solid #3e3e42 !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }
    .stButton>button[kind="secondary"]:hover {
        border-color: #8c8c8c !important;
        background-color: rgba(255,255,255,0.05) !important;
    }

    /* กล่องข้อมูล (Metric Cards) แบบเรียบแบน */
    .metric-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #1c1c1c;
        padding: 1.25rem;
        border-radius: 8px;
        border: 1px solid #2e2e2e;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #8c8c8c;
        font-weight: 400;
        margin-bottom: 0.25rem;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 500;
        color: #ededed;
    }

    /* แท็บเมนู (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 1px solid #2e2e2e;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        padding: 0;
        font-size: 0.9rem;
        font-weight: 400;
        color: #8c8c8c;
        border: none;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #ededed !important;
        border-bottom: 2px solid #24b47e !important;
    }

    /* ฟอร์มและกล่อง Input */
    div[data-testid="stForm"] {
        background-color: #1c1c1c;
        border: 1px solid #2e2e2e;
        border-radius: 8px;
        padding: 1.5rem;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stDateInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea {
        background-color: #141414 !important;
        border: 1px solid #3e3e42 !important;
        border-radius: 6px !important;
        color: #ededed !important;
    }
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
        border-color: #24b47e !important;
        box-shadow: none !important;
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
        return "ข้อมูลไม่ถูกต้อง", 0, "none"

# -------------------------------------------------------------
# Pop-up Dialogs
# -------------------------------------------------------------
@st.dialog("ตั้งค่าระบบและสาขา")
def manage_org_modal(current_hosp_name, branch_list, current_branch):
    tab_h, tab_b = st.tabs(["ตั้งชื่อระบบ", "จัดการสาขา"])
    
    with tab_h:
        with st.form("hosp_name_form"):
            new_hosp = st.text_input("ชื่อระบบ / โรงพยาบาล", value=current_hosp_name)
            if st.form_submit_button("บันทึกการเปลี่ยนแปลง", type="primary", use_container_width=True):
                if new_hosp.strip():
                    db.update_hospital_name(new_hosp.strip())
                    st.success("บันทึกข้อมูลสำเร็จ")
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
                        st.success("อัปเดตสำเร็จ")
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
                        st.success("สร้างสาขาสำเร็จ")
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
                        st.success("ลบสาขาสำเร็จ")
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
                st.success("บันทึกข้อมูลสำเร็จ")
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
            st.success("ลบข้อมูลสำเร็จ")
            st.rerun()
    with col2:
        if st.button("ยกเลิก", use_container_width=True):
            st.rerun()

# -------------------------------------------------------------
# โหลดข้อมูล
# -------------------------------------------------------------
hospital_name = db.get_hospital_name()
BRANCH_LIST = db.get_branches()

col_header, col_branch = st.columns([3, 1])

# สลับลำดับให้ col_branch ทำงานก่อนเพื่อสร้างตัวแปร selected_branch
with col_branch:
    selected_branch = st.selectbox(
        "เลือกสาขา",
        options=BRANCH_LIST,
        key="branch_selector",
        label_visibility="collapsed"
    )
    if st.button("ตั้งค่าระบบ", use_container_width=True):
        manage_org_modal(hospital_name, BRANCH_LIST, selected_branch)

# ค่อยนำ selected_branch มาแสดงผลใน col_header
with col_header:
    st.markdown(f"<h1 style='font-size: 1.5rem; margin-bottom: 0;'>{hospital_name}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #8c8c8c; font-size: 0.9rem;'>พื้นที่ปฏิบัติงาน: {selected_branch}</p>", unsafe_allow_html=True)

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
        <div class="metric-card">
            <div class="metric-title">เครื่องจักรทั้งหมด</div>
            <div class="metric-value">{total_eq}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">ประวัติการตรวจสอบ</div>
            <div class="metric-value">{total_services}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title" style="color:#f59e0b;">ใกล้ครบกำหนด</div>
            <div class="metric-value">{warning_cnt}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title" style="color:#ef4444;">เลยกำหนด</div>
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
    st.markdown("<h3 style='font-size:1.1rem; margin-bottom:1rem;'>ลงทะเบียนเครื่องจักรใหม่</h3>", unsafe_allow_html=True)
    
    default_types = ["Autoclave", "ETO", "Plasma Sterilizer", "Washer Disinfector"]
    existing_types = [t for t in df_equipments["type"].unique() if t not in default_types] if not df_equipments.empty else []
    all_type_options = default_types + existing_types + ["ระบุประเภทอื่น..."]

    with st.form("add_equipment_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_code = st.text_input("รหัสอุปกรณ์ *")
            new_name = st.text_input("ชื่ออุปกรณ์ *")
            selected_type = st.selectbox("ประเภทเครื่อง *", options=all_type_options)
            custom_type = st.text_input("ระบุประเภท (กรณีเลือก 'ระบุประเภทอื่น...')")
        with c2:
            new_brand = st.text_input("ยี่ห้อ / รุ่น")
            new_loc = st.text_input("แผนก / จุดติดตั้ง")
            new_pm_freq = st.number_input("รอบ PM (เดือน)", min_value=1, value=6)
        with c3:
            new_cal_freq = st.number_input("รอบ Calibration (เดือน)", min_value=1, value=12)
            last_pm = st.date_input("วันที่ PM ล่าสุด (ถ้ามี)", value=None)
            last_cal = st.date_input("วันที่ Calibrate ล่าสุด (ถ้ามี)", value=None)

        if st.form_submit_button("บันทึกข้อมูล", type="primary"):
            final_type = custom_type.strip() if selected_type == "ระบุประเภทอื่น..." else selected_type
            if not new_code.strip() or not new_name.strip() or not final_type:
                st.error("กรุณากรอกข้อมูลบังคับ (*) ให้ครบถ้วน")
            else:
                try:
                    db.add_equipment(
                        new_code.strip(), new_name.strip(), final_type,
                        new_brand.strip(), new_loc.strip(),
                        int(new_pm_freq), int(new_cal_freq),
                        str(last_pm) if last_pm else None,
                        str(last_cal) if last_cal else None,
                        branch=selected_branch
                    )
                    st.success("บันทึกข้อมูลสำเร็จ")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    if not df_equipments.empty:
        st.markdown("<br><h3 style='font-size:1.1rem; margin-bottom:1rem;'>ลบข้อมูลเครื่องจักร</h3>", unsafe_allow_html=True)
        del_options = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1:
            selected_del = st.selectbox("เลือกอุปกรณ์", list(del_options.keys()), label_visibility="collapsed")
        with c_del2:
            if st.button("ลบข้อมูล", type="secondary", use_container_width=True):
                db.delete_equipment(int(del_options[selected_del]))
                st.success("ลบข้อมูลสำเร็จ")
                st.rerun()

# =============================================================
# TAB 3: บันทึกผล PM / Calibration
# =============================================================
with tab_log:
    st.markdown("<h3 style='font-size:1.1rem; margin-bottom:1rem;'>บันทึกประวัติการตรวจสอบ</h3>", unsafe_allow_html=True)
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

            if st.form_submit_button("บันทึกประวัติ", type="primary"):
                if not technician.strip():
                    st.error("กรุณาระบุผู้ดำเนินการ")
                else:
                    eq_id = int(eq_options[selected_label])
                    if db.check_duplicate_service(eq_id, task_type, str(service_date)):
                        st.warning("มีประวัติในระบบแล้ว")
                    else:
                        db.log_service(eq_id, task_type, str(service_date), technician.strip(), result, remarks.strip())
                        st.success("บันทึกข้อมูลสำเร็จ")
                        st.rerun()

# =============================================================
# TAB 4: ประวัติและแก้ไข
# =============================================================
with tab_history:
    if df_equipments.empty:
        st.info("ไม่พบข้อมูล")
    else:
        eq_map = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        selected_history_eq = st.selectbox("ค้นหาประวัติอุปกรณ์", list(eq_map.keys()))
        
        selected_id = int(eq_map[selected_history_eq])
        eq_records = df_records[df_records["equipment_id"] == selected_id] if not df_records.empty else pd.DataFrame()

        if eq_records.empty:
            st.info("ไม่มีประวัติการดำเนินการ")
        else:
            st.dataframe(
                eq_records[["id", "task_type", "service_date", "technician", "result", "remarks"]],
                hide_index=True,
                use_container_width=True
            )

            st.markdown("<br><p style='font-size:0.9rem; color:#8c8c8c;'>จัดการข้อมูล</p>", unsafe_allow_html=True)
            rec_options = {f"{r['service_date']} | {r['task_type']} | {r['result']}": r for _, r in eq_records.iterrows()}
            c_rec1, c_rec2, c_rec3 = st.columns([2, 1, 1])
            with c_rec1:
                rec_choice = st.selectbox("เลือกรายการ", list(rec_options.keys()), label_visibility="collapsed")
                target_record = rec_options[rec_choice]
            with c_rec2:
                if st.button("แก้ไขรายการ", use_container_width=True):
                    edit_record_modal(target_record)
            with c_rec3:
                if st.button("ลบรายการ", type="secondary", use_container_width=True):
                    delete_record_modal(target_record["id"], f"{target_record['task_type']}")

# =============================================================
# TAB 5: คำนวณรอบล่วงหน้า
# =============================================================
with tab_calc:
    st.markdown("<h3 style='font-size:1.1rem; margin-bottom:1rem;'>ระบบจำลองการคำนวณรอบ</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        base_date = st.date_input("วันที่เริ่มต้น")
        freq_month = st.number_input("ความถี่ (เดือน)", min_value=1, value=6)
    with c2:
        calc_result = base_date + relativedelta(months=int(freq_month))
        st.markdown(f"""
        <div style="background-color: #1c1c1c; padding: 1.5rem; border-radius: 8px; border: 1px solid #2e2e2e; margin-top: 1.7rem;">
            <div style="color: #8c8c8c; font-size: 0.85rem;">วันที่ครบกำหนดรอบถัดไป</div>
            <div style="font-size: 2rem; font-weight: 500; color: #24b47e;">{calc_result.strftime('%d/%m/%Y')}</div>
        </div>
        """, unsafe_allow_html=True)
