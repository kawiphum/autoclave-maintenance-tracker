import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import database as db

st.set_page_config(page_title="Maintenance System", layout="wide", initial_sidebar_state="collapsed")

# -------------------------------------------------------------
# 1. ระบบจัดการ Session State (Login)
# -------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.branch = ""

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

def trigger_notification(message):
    st.session_state["success_msg"] = message

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.branch = ""
    st.session_state.auth_mode = "login"
    st.rerun()

# -------------------------------------------------------------
# 2. Custom CSS
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@400;500;600&family=Sarabun:wght@300;400;500;600&display=swap');
    
    .stApp, [data-testid="stAppViewContainer"], .stDialog > div { background-color: #0f172a !important; }
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown { color: #f8fafc !important; }
    
    /* บังคับเฉพาะตัวหนังสือหลัก ไม่ให้กระทบปุ่มรูปลูกตา (visibili) */
    html, body, .stMarkdown, .stText, p, div, input, select, textarea { font-family: 'Sarabun', sans-serif; }
    h1, h2, h3, h4, h5, h6, .metric-value, .stTabs [data-baseweb="tab"] { font-family: 'Prompt', sans-serif !important; }
    #MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden;}

    /* คืนค่าฟอนต์ไอคอนให้ระบบของ Streamlit ป้องกันคำว่า visibili */
    button[title="Show password text"], button[title="Hide password text"], div[data-baseweb="input"] button {
        font-family: inherit !important;
    }

    button[kind="primary"] { font-family: 'Sarabun', sans-serif !important; background-color: #059669 !important; color: #ffffff !important; border: 1px solid #059669 !important; border-radius: 6px !important; font-weight: 600 !important; padding: 0.5rem 1.5rem !important; transition: all 0.2s ease; }
    button[kind="primary"]:hover { background-color: #047857 !important; border-color: #047857 !important; }
    button[kind="secondary"] { font-family: 'Sarabun', sans-serif !important; background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; border-radius: 6px !important; font-weight: 500 !important; }
    button[kind="secondary"]:hover { background-color: #475569 !important; border-color: #64748b !important; }

    .metric-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 1.5rem; }
    .metric-card { background-color: #1e293b; padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; }
    .metric-title { font-size: 1rem; color: #94a3b8; margin-bottom: 0.5rem; }
    .metric-value { font-size: 2rem; font-weight: 600; color: #f8fafc; }
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; border-bottom: 1px solid #334155; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding: 0; font-size: 1.05rem; color: #94a3b8; border: none; background: transparent; }
    .stTabs [aria-selected="true"] { color: #f8fafc !important; border-bottom: 3px solid #059669 !important; }

    div[data-testid="stForm"] { background-color: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 2rem; }
    div[data-baseweb="base-input"], div[data-baseweb="input"], div[data-baseweb="select"] > div, 
    textarea, input, .stDateInput input, .stTextInput input, .stNumberInput input {
        background-color: #1e293b !important; color: #f8fafc !important; -webkit-text-fill-color: #f8fafc !important; border: 1px solid #475569 !important; border-radius: 6px !important; padding: 0.5rem !important;
    }
    input:focus, textarea:focus, div[data-baseweb="select"] > div:focus { border-color: #059669 !important; box-shadow: 0 0 0 1px #059669 !important; }
    div[data-baseweb="calendar"], div[data-baseweb="popover"] { background-color: #1e293b !important; border: 1px solid #334155 !important; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 3. หน้าล็อกอิน & สมัครสมาชิก
# -------------------------------------------------------------
BRANCH_LIST = db.get_branches()
hospital_name = db.get_hospital_name()

if not st.session_state.logged_in:
    st.markdown("""
    <style>
        .stApp { background-color: #121212; }
        div[data-testid="stForm"] { background-color: #1e1e1e !important; border: none !important; border-radius: 24px !important; padding: 2.5rem 2rem !important; }
        .stTextInput>div>div>input, .stSelectbox>div>div>div { background-color: #2d2d2d !important; border: none !important; border-radius: 12px !important; color: #ffffff !important; padding: 0.8rem 1rem !important; }
        button[kind="primary"] { background-color: #3a3a3a !important; color: #ffffff !important; border: none !important; border-radius: 12px !important; padding: 0.8rem !important; font-weight: 600 !important; margin-top: 1rem !important; }
        button[kind="primary"]:hover { background-color: #4a4a4a !important; }
        .toggle-btn button { background-color: transparent !important; color: #888888 !important; border: none !important; font-size: 0.9rem !important; }
        .toggle-btn button:hover { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

    col_img1, col_img2, col_img3 = st.columns([1, 0.15, 1])
    with col_img2:
        try:
            st.image("logo.png", use_column_width=True)
        except:
            st.markdown("""<div style="width: 50px; height: 50px; border-radius: 50%; background: linear-gradient(135deg, #ffffff 0%, #a3a3a3 100%); display: flex; align-items: center; justify-content: center; margin: auto;"><div style="width: 44px; height: 44px; border-radius: 50%; background: #1c1c1e; display: flex; align-items: center; justify-content: center;"><span style="color: #fff; font-size: 1.2rem; font-weight: bold;">M</span></div></div>""", unsafe_allow_html=True)
    
    st.markdown(f"<h2 style='text-align: center; color: white; font-family: Prompt; margin-bottom: 2rem;'>{hospital_name}</h2>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        if st.session_state.auth_mode == "login":
            with st.form("login_form"):
                user = st.text_input("ชื่อผู้ใช้งาน (Username)")
                pw = st.text_input("รหัสผ่าน (Password)", type="password")
                if st.form_submit_button("เข้าสู่ระบบ (Sign in)", type="primary", use_container_width=True):
                    user_data = db.login_user(user.strip(), pw.strip())
                    if user_data:
                        st.session_state.logged_in = True
                        st.session_state.username = user.strip()
                        st.session_state.role = user_data["role"]
                        st.session_state.branch = user_data["branch"]
                        st.rerun()
                    else:
                        st.error("ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")
            
            st.markdown("<div class='toggle-btn' style='text-align: center; margin-top: 1rem;'>", unsafe_allow_html=True)
            if st.button("ยังไม่มีบัญชี? สมัครสมาชิก (Sign up, it's free!)", use_container_width=True):
                st.session_state.auth_mode = "register"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        else:
            with st.form("reg_form"):
                st.markdown("<p style='color:#888; text-align:center;'>สมาชิกใหม่จะได้รับสิทธิ์เป็น 'ผู้ใช้งานทั่วไป'</p>", unsafe_allow_html=True)
                new_user = st.text_input("ตั้งชื่อผู้ใช้งาน")
                new_pw = st.text_input("ตั้งรหัสผ่าน", type="password")
                confirm_pw = st.text_input("ยืนยันรหัสผ่าน", type="password")
                sel_branch = st.selectbox("เลือกสาขาที่ปฏิบัติงาน", BRANCH_LIST)
                
                if st.form_submit_button("ยืนยันสมัครสมาชิก (Sign up)", type="primary", use_container_width=True):
                    if new_user and new_pw and confirm_pw:
                        if new_pw != confirm_pw:
                            st.error("รหัสผ่านไม่ตรงกัน กรุณาตรวจสอบอีกครั้ง")
                        else:
                            if db.register_user(new_user.strip(), new_pw.strip(), sel_branch):
                                st.success("สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ")
                                st.session_state.auth_mode = "login"
                            else:
                                st.error("ชื่อผู้ใช้งานนี้มีคนใช้แล้ว")
                    else:
                        st.error("กรุณากรอกข้อมูลให้ครบถ้วน")

            st.markdown("<div class='toggle-btn' style='text-align: center; margin-top: 1rem;'>", unsafe_allow_html=True)
            if st.button("มีบัญชีแล้ว? เข้าสู่ระบบ (Sign in)", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.stop() 

# -------------------------------------------------------------
# 4. ฟังก์ชันหลักสำหรับคนล็อกอินแล้ว
# -------------------------------------------------------------
def calculate_status(due_date_str):
    if not due_date_str: return "ไม่มีข้อมูล", 0, "none"
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (due_date - today).days
        if days_left < 0: return f"เลยกำหนด ({abs(days_left)} วัน)", 0, "overdue"
        elif days_left <= 15: return f"ใกล้ครบกำหนด ({days_left} วัน)", max(0, min(100, int((days_left / 15) * 100))), "warning"
        else: return f"ปกติ ({days_left} วัน)", 100, "normal"
    except: return "ข้อมูลไม่ถูกต้อง", 0, "none"

@st.dialog("ตั้งค่าระบบและสาขา")
def manage_org_modal(hosp_name, branches, current_branch, role):
    if role == "super_admin":
        tabs = st.tabs(["ข้อมูลระบบ", "จัดการสาขา", "👑 จัดการผู้ใช้งาน"])
    else:
        tabs = st.tabs(["จัดการสาขา"])

    if role == "super_admin":
        with tabs[0]:
            with st.form("hosp_form"):
                new_hosp = st.text_input("ชื่อระบบ", value=hosp_name)
                if st.form_submit_button("บันทึก", type="primary", use_container_width=True):
                    db.update_hospital_name(new_hosp.strip())
                    trigger_notification("อัปเดตชื่อระบบสำเร็จ")
                    st.rerun()

 tab_b = tabs[1] if role == "super_admin" else tabs[0]
    with tab_b:
        with st.form("rename_form"):
            # 🛑 จำกัดสิทธิ์แอดมิน: ให้เลือกเปลี่ยนชื่อได้เฉพาะสาขาตัวเองเท่านั้น
            if role == "super_admin":
                target_b = st.selectbox("เปลี่ยนชื่อสาขาเดิม", branches, index=branches.index(current_branch) if current_branch in branches else 0)
            else:
                st.text_input("สาขาที่ต้องการเปลี่ยนชื่อ (จำกัดสิทธิ์เฉพาะสาขาของคุณ)", value=current_branch, disabled=True)
                target_b = current_branch
                
            new_b = st.text_input("ชื่อใหม่")
            if st.form_submit_button("บันทึกชื่อใหม่", type="primary", use_container_width=True):
                if new_b.strip() and new_b.strip() != target_b:
                    db.rename_branch(target_b, new_b.strip())
                    if st.session_state.branch == target_b: st.session_state.branch = new_b.strip()
                    trigger_notification("เปลี่ยนชื่อสาขาสำเร็จ")
                    st.rerun()
                    
        if role == "super_admin":
            with st.form("add_b_form"):
                add_b = st.text_input("เพิ่มสาขาใหม่")
                if st.form_submit_button("สร้างสาขา", use_container_width=True):
                    if add_b.strip():
                        db.add_branch(add_b.strip())
                        trigger_notification("สร้างสาขาเรียบร้อย")
                        st.rerun()

            if len(branches) > 1:
                with st.form("del_b_form"):
                    del_b = st.selectbox("เลือกลบสาขา", branches)
                    if st.form_submit_button("ลบสาขานี้", type="secondary", use_container_width=True):
                        db.delete_branch(del_b)
                        if st.session_state.branch == del_b: st.session_state.branch = branches[0]
                        trigger_notification("ลบสาขาสำเร็จ")
                        st.rerun()

    if role == "super_admin":
        with tabs[2]:
            users_df = db.get_all_users()
            
            st.markdown("<p style='font-weight:600; margin-bottom:0.5rem; color:#94A3B8;'>กรองรายชื่อตามสาขา</p>", unsafe_allow_html=True)
            filter_branch = st.selectbox("เลือกสาขาที่ต้องการดู", ["ทั้งหมด"] + branches, key="filter_branch_sel")
            
            if filter_branch != "ทั้งหมด":
                users_df = users_df[users_df['branch'] == filter_branch]
                
            if users_df.empty:
                st.info("ไม่มีบัญชีผู้ใช้งานในสาขานี้")
            else:
                user_opts = {f"👤 {r['username']} (ยศ: {r['role']} | สาขา: {r['branch']})": r['id'] for _, r in users_df.iterrows()}
                
                st.markdown("<hr style='border-color: #334155; margin: 1.5rem 0;'>", unsafe_allow_html=True)
                st.markdown("<p style='font-weight:600; margin-bottom:0.5rem; color:#94A3B8;'>มอบยศ / เปลี่ยนสาขา</p>", unsafe_allow_html=True)
                
                sel_u = st.selectbox("เลือกบัญชีผู้ใช้", list(user_opts.keys()), key="edit_user_sel")
                target_uid = user_opts[sel_u]
                curr_u = users_df[users_df['id'] == target_uid].iloc[0]
                
                new_r = st.selectbox("กำหนดระดับสิทธิ์ (Role)", ["user", "admin", "super_admin"], index=["user", "admin", "super_admin"].index(curr_u['role']), key="role_sel")
                b_idx = branches.index(curr_u['branch']) if curr_u['branch'] in branches else 0
                new_b = st.selectbox("สาขาที่รับผิดชอบ", branches, index=b_idx, key="branch_sel")
                
                if st.button("บันทึกการเปลี่ยนแปลงสิทธิ์", type="primary", use_container_width=True):
                    db.update_user_role_branch(target_uid, new_r, new_b)
                    trigger_notification("อัปเดตสิทธิ์ผู้ใช้งานสำเร็จ")
                    st.rerun()

                st.markdown("<br><p style='font-weight:600; margin-bottom:0.5rem; color:#EF4444;'>ลบบัญชีผู้ใช้งาน</p>", unsafe_allow_html=True)
                del_u = st.selectbox("เลือกบัญชีที่ต้องการลบ", list(user_opts.keys()), key="del_user_sel")
                if st.button("ลบบัญชีนี้", type="secondary", use_container_width=True):
                    del_uid = user_opts[del_u]
                    target_username = users_df[users_df['id'] == del_uid].iloc[0]['username']
                    
                    if target_username == st.session_state.username:
                        st.error("ไม่อนุญาตให้ลบบัญชีของตัวเองที่กำลังใช้งานอยู่ได้")
                    else:
                        db.delete_user(del_uid)
                        trigger_notification(f"ลบบัญชี {target_username} ออกจากระบบแล้ว")
                        st.rerun()

@st.dialog("แก้ไขประวัติ")
def edit_record_modal(record):
    with st.form("modal_edit_form"):
        new_date = st.date_input("วันที่ดำเนินการ", value=datetime.strptime(record["service_date"], "%Y-%m-%d").date())
        new_tech = st.text_input("ผู้ดำเนินการ", value=record["technician"] or "")
        res_list = ["Passed", "Passed with Condition", "Failed"]
        curr_idx = res_list.index(record["result"]) if record["result"] in res_list else 0
        new_res = st.selectbox("ผลการตรวจสอบ", res_list, index=curr_idx)
        new_rem = st.text_area("หมายเหตุ", value=record["remarks"] or "")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.form_submit_button("บันทึก", type="primary", use_container_width=True):
                db.update_service_record(int(record["id"]), str(new_date), new_tech.strip(), new_res, new_rem.strip())
                trigger_notification("แก้ไขประวัติสำเร็จ")
                st.rerun()
        with c2:
            if st.form_submit_button("ยกเลิก", use_container_width=True): st.rerun()

@st.dialog("ยืนยันการลบ")
def delete_record_modal(record_id, task_title):
    st.write(f"ต้องการลบรายการ {task_title} ใช่หรือไม่?")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("ยืนยัน", type="primary", use_container_width=True):
            db.delete_service_record(int(record_id))
            trigger_notification("ลบสำเร็จ")
            st.rerun()
    with c2:
        if st.button("ยกเลิก", use_container_width=True): st.rerun()

# -------------------------------------------------------------
# Layout ของเว็บเมื่อล็อกอินแล้ว
# -------------------------------------------------------------
col_h1, col_h2, col_h3 = st.columns([4, 2, 1])
with col_h1:
    c_logo, c_text = st.columns([0.25, 1]) 
    with c_logo:
        try:
            st.image("logo.png", use_column_width=True)
        except:
            pass
    with c_text:
        st.markdown(f"<h1 style='font-size: 1.8rem; margin-bottom: 0.2rem; margin-top: 0;'>{hospital_name}</h1>", unsafe_allow_html=True)
        
        if st.session_state.role == "super_admin":
            if st.session_state.branch not in BRANCH_LIST: st.session_state.branch = BRANCH_LIST[0] if BRANCH_LIST else ""
            sel_b = st.selectbox("สลับดูสาขา (สิทธิ์เจ้าของระบบ):", BRANCH_LIST, index=BRANCH_LIST.index(st.session_state.branch))
            if sel_b != st.session_state.branch:
                st.session_state.branch = sel_b
                st.rerun()
        else:
            role_th = "แอดมินสาขา" if st.session_state.role == "admin" else "ผู้ใช้งานทั่วไป"
            st.markdown(f"<p style='color: #94A3B8; font-size: 1rem; margin-top: -5px;'>พื้นที่ปฏิบัติงาน: <b>{st.session_state.branch}</b> <span style='color:#10B981;'>[{role_th}]</span></p>", unsafe_allow_html=True)

with col_h2:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    if st.session_state.role in ["admin", "super_admin"]:
        if st.button("⚙️ ตั้งค่าระบบ", use_container_width=True):
            manage_org_modal(hospital_name, BRANCH_LIST, st.session_state.branch, st.session_state.role)

with col_h3:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    if st.button("🚪 ออกจากระบบ", type="secondary", use_container_width=True):
        logout()

# แจ้งเตือนกลางจอ
noti_container = st.container()
with noti_container:
    if "success_msg" in st.session_state:
        st.success(st.session_state["success_msg"])
        del st.session_state["success_msg"]
    else:
        st.markdown("<div style='height: 0px;'></div>", unsafe_allow_html=True)

df_equipments, df_records = db.get_branch_data_cached(st.session_state.branch)

tab_overview, tab_manage, tab_log, tab_history, tab_calc = st.tabs([
    "ภาพรวมระบบ", "ทะเบียนเครื่องจักร", "บันทึกผลตรวจสอบ", "ประวัติข้อมูล", "คำนวณรอบ"
])

# =============================================================
with tab_overview:
    total_eq = len(df_equipments)
    total_services = len(df_records)
    overdue_cnt = warning_cnt = 0
    processed_rows = []

    if not df_equipments.empty:
        for _, row in df_equipments.iterrows():
            pm_status, pm_prog, pm_type = calculate_status(row["next_pm_date"])
            cal_status, cal_prog, cal_type = calculate_status(row["next_cal_date"])
            if pm_type == "overdue" or cal_type == "overdue": overdue_cnt += 1
            elif pm_type == "warning" or cal_type == "warning": warning_cnt += 1
            processed_rows.append({"รหัส": row["equipment_code"], "ชื่ออุปกรณ์": row["name"], "ประเภท": row["type"], "แผนก": row["location"] or "-", "PM (รอบถัดไป)": row["next_pm_date"] or "-", "สถานะ PM": pm_status, "Cal (รอบถัดไป)": row["next_cal_date"] or "-", "สถานะ Cal": cal_status})

    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card"><div class="metric-title">เครื่องจักรทั้งหมด</div><div class="metric-value" style="color:#10B981;">{total_eq}</div></div>
        <div class="metric-card"><div class="metric-title">ประวัติการตรวจสอบ</div><div class="metric-value" style="color:#3B82F6;">{total_services}</div></div>
        <div class="metric-card"><div class="metric-title">ใกล้ครบกำหนด</div><div class="metric-value" style="color:#F59E0B;">{warning_cnt}</div></div>
        <div class="metric-card"><div class="metric-title">เลยกำหนด</div><div class="metric-value" style="color:#EF4444;">{overdue_cnt}</div></div>
    </div>
    """, unsafe_allow_html=True)

    if df_equipments.empty:
        st.info("ไม่มีข้อมูลในระบบ")
    else:
        view_df = pd.DataFrame(processed_rows)
        c1, c2 = st.columns([1, 1])
        with c1: selected_types = st.multiselect("กรองตามประเภท:", options=list(df_equipments["type"].unique()), default=list(df_equipments["type"].unique()))
        with c2: search_text = st.text_input("ค้นหาจากรหัสหรือชื่ออุปกรณ์:")

        filtered_df = view_df[view_df["ประเภท"].isin(selected_types)]
        if search_text: filtered_df = filtered_df[filtered_df["รหัส"].str.contains(search_text, case=False, na=False) | filtered_df["ชื่ออุปกรณ์"].str.contains(search_text, case=False, na=False)]
        st.dataframe(filtered_df, hide_index=True, use_container_width=True)

# =============================================================
with tab_manage:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1rem;'>ลงทะเบียนเครื่องจักรใหม่</h3>", unsafe_allow_html=True)
    all_type_options = ["Autoclave", "ETO", "Plasma Sterilizer", "Washer Disinfector"] + ([t for t in df_equipments["type"].unique() if t not in ["Autoclave", "ETO", "Plasma Sterilizer", "Washer Disinfector"]] if not df_equipments.empty else []) + ["ระบุประเภทอื่น..."]

    col_t1, col_t2 = st.columns(2)
    with col_t1: selected_type = st.selectbox("ประเภทเครื่อง", options=all_type_options, key="manage_type_sel")
    custom_type = st.text_input("พิมพ์ชื่อประเภทเครื่องใหม่", key="manage_type_custom") if selected_type == "ระบุประเภทอื่น..." else selected_type

    with st.form("add_equipment_form", clear_on_submit=True):
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

        if st.form_submit_button("บันทึกข้อมูลเครื่องจักร", type="primary"):
            if not new_code.strip() or not new_name.strip() or not custom_type.strip(): st.error("กรุณากรอกข้อมูลบังคับ (*) ให้ครบถ้วน")
            else:
                db.add_equipment(new_code.strip(), new_name.strip(), custom_type.strip(), new_brand.strip(), new_loc.strip(), int(new_pm_freq), int(new_cal_freq), str(last_pm) if last_pm else None, str(last_cal) if last_cal else None, st.session_state.branch)
                trigger_notification("ลงทะเบียนเรียบร้อย")
                st.rerun()

    if not df_equipments.empty:
        st.markdown("<br><h3 style='font-size:1.2rem; margin-bottom:1rem;'>ลบข้อมูลเครื่องจักร</h3>", unsafe_allow_html=True)
        del_options = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1: selected_del = st.selectbox("เลือกอุปกรณ์", list(del_options.keys()), label_visibility="collapsed", key="manage_del_sel")
        with c_del2:
            if st.button("ลบข้อมูล", type="secondary", use_container_width=True):
                db.delete_equipment(int(del_options[selected_del]))
                trigger_notification("ลบข้อมูลสำเร็จ")
                st.rerun()

# =============================================================
with tab_log:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1rem;'>บันทึกประวัติการตรวจสอบ</h3>", unsafe_allow_html=True)
    if df_equipments.empty: st.info("ไม่พบข้อมูลเครื่องจักร")
    else:
        eq_options = {f"[{row['equipment_code']}] {row['name']}": row['id'] for _, row in df_equipments.iterrows()}
        with st.form("service_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                selected_label = st.selectbox("อุปกรณ์ *", list(eq_options.keys()), key="log_eq_sel")
                task_type = st.radio("ประเภทงาน *", ["PM", "Calibration"], horizontal=True)
                service_date = st.date_input("วันที่ดำเนินการ *", value=date.today())
            with col2:
                technician = st.text_input("ผู้ดำเนินการ *", placeholder="ระบุชื่อช่าง/ผู้ดำเนินการ")
                result = st.selectbox("ผลการตรวจสอบ *", ["Passed", "Passed with Condition", "Failed"])
                remarks = st.text_area("หมายเหตุ")
            if st.form_submit_button("บันทึกประวัติ", type="primary"):
                if not technician.strip(): st.error("กรุณาระบุผู้ดำเนินการ")
                else:
                    if db.check_duplicate_service(int(eq_options[selected_label]), task_type, str(service_date)): 
                        st.warning("มีประวัติในระบบแล้ว")
                    else:
                        db.log_service(int(eq_options[selected_label]), task_type, str(service_date), technician.strip(), result, remarks.strip())
                        trigger_notification("บันทึกสำเร็จ")
                        st.rerun()

# =============================================================
with tab_history:
    st.markdown("<h3 style='font-size:1.2rem; margin-bottom:1rem;'>ค้นหาและแก้ไขประวัติ</h3>", unsafe_allow_html=True)
    if df_equipments.empty: st.info("ไม่พบข้อมูล")
    else:
        eq_map = {f"[{r['equipment_code']}] {r['name']}": r['id'] for _, r in df_equipments.iterrows()}
        selected_history_eq = st.selectbox("ค้นหาประวัติอุปกรณ์", list(eq_map.keys()), label_visibility="collapsed", key="history_eq_sel")
        eq_records = df_records[df_records["equipment_id"] == int(eq_map[selected_history_eq])] if not df_records.empty else pd.DataFrame()

        if eq_records.empty: st.info("ไม่มีประวัติ")
        else:
            pm_records = eq_records[eq_records["task_type"] == "PM"].copy()
            cal_records = eq_records[eq_records["task_type"] == "Calibration"].copy()

            st.markdown(f"""
            <div style='display: flex; gap: 1rem; margin-bottom: 1.2rem;'>
                <div style='background-color: #1e293b; padding: 0.8rem 1.2rem; border-radius: 6px; border: 1px solid #334155; width: 50%;'>
                    <div style='color: #94A3B8; font-size: 0.9rem;'>ยอดรวม PM สะสม</div>
                    <div style='color: #10B981; font-size: 1.5rem; font-weight: 600;'>{len(pm_records)} <span style='font-size: 0.9rem; font-weight: 400; color: #94A3B8;'>ครั้ง</span></div>
                </div>
                <div style='background-color: #1e293b; padding: 0.8rem 1.2rem; border-radius: 6px; border: 1px solid #334155; width: 50%;'>
                    <div style='color: #94A3B8; font-size: 0.9rem;'>ยอดรวม Calibration สะสม</div>
                    <div style='color: #3B82F6; font-size: 1.5rem; font-weight: 600;'>{len(cal_records)} <span style='font-size: 0.9rem; font-weight: 400; color: #94A3B8;'>ครั้ง</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<h4 style='color:#10B981; font-size:1.1rem; margin-top: 1.5rem; margin-bottom: 0.5rem;'>ประวัติ Preventive Maintenance (PM)</h4>", unsafe_allow_html=True)
            if pm_records.empty:
                st.info("ไม่มีประวัติ PM")
            else:
                pm_records = pm_records.sort_values(by=["service_date", "id"], ascending=[False, False]).reset_index(drop=True)
                pm_records.insert(0, 'ลำดับ', range(1, len(pm_records) + 1))
                st.dataframe(pm_records[["ลำดับ", "service_date", "technician", "result", "remarks"]], hide_index=True, use_container_width=True)

            st.markdown("<h4 style='color:#3B82F6; font-size:1.1rem; margin-top: 2rem; margin-bottom: 0.5rem;'>ประวัติ Calibration</h4>", unsafe_allow_html=True)
            if cal_records.empty:
                st.info("ไม่มีประวัติ Calibration")
            else:
                cal_records = cal_records.sort_values(by=["service_date", "id"], ascending=[False, False]).reset_index(drop=True)
                cal_records.insert(0, 'ลำดับ', range(1, len(cal_records) + 1))
                st.dataframe(cal_records[["ลำดับ", "service_date", "technician", "result", "remarks"]], hide_index=True, use_container_width=True)

            st.markdown("<br><p style='font-size:1rem; color:#94A3B8; margin-bottom:0.5rem;'>จัดการข้อมูลประวัติ</p>", unsafe_allow_html=True)
            rec_options = {f"{r['service_date']} | {r['task_type']} | {r['result']}": r for _, r in eq_records.iterrows()}
            c_rec1, c_rec2, c_rec3 = st.columns([2, 1, 1])
            with c_rec1: target_record = rec_options[st.selectbox("เลือกรายการ", list(rec_options.keys()), label_visibility="collapsed", key="history_rec_sel")]
            with c_rec2:
                if st.button("แก้ไขรายการ", type="primary", use_container_width=True): edit_record_modal(target_record)
            with c_rec3:
                if st.button("ลบรายการ", type="secondary", use_container_width=True): delete_record_modal(target_record["id"], target_record['task_type'])

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
