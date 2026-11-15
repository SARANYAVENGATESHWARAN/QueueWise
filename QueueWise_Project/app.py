import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from pathlib import Path
import math

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "data" / "queuewise.db"
DB_PATH.parent.mkdir(exist_ok=True)

st.set_page_config(page_title="QueueWise", page_icon="🎟️", layout="wide")

def connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with connect() as con:
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS counters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_no TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            service_type TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            counter_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Waiting',
            created_at TEXT NOT NULL,
            called_at TEXT,
            completed_at TEXT,
            estimated_minutes INTEGER DEFAULT 0,
            FOREIGN KEY(counter_id) REFERENCES counters(id)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS service_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id INTEGER NOT NULL,
            duration_minutes REAL NOT NULL,
            service_date TEXT NOT NULL,
            FOREIGN KEY(token_id) REFERENCES tokens(id)
        )""")
        cur.execute("SELECT COUNT(*) FROM counters")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO counters(name, is_active) VALUES (?,1)",
                            [("Counter 1",), ("Counter 2",), ("Counter 3",)])
        con.commit()

def read_df(query, params=()):
    with connect() as con:
        return pd.read_sql_query(query, con, params=params)

def execute(query, params=()):
    with connect() as con:
        cur=con.cursor()
        cur.execute(query, params)
        con.commit()
        return cur.lastrowid

def get_avg_service():
    df=read_df("SELECT duration_minutes FROM service_times ORDER BY id DESC LIMIT 50")
    if df.empty:
        return 5.0
    return max(1.0, float(df["duration_minutes"].mean()))

def next_token_number():
    today=date.today().strftime("%y%m%d")
    df=read_df("SELECT token_no FROM tokens WHERE token_no LIKE ?", (f"Q{today}-%",))
    return f"Q{today}-{len(df)+1:03d}"

def waiting_estimate(token_id):
    token=read_df("SELECT * FROM tokens WHERE id=?", (token_id,))
    if token.empty:
        return 0
    row=token.iloc[0]
    avg=get_avg_service()
    if row["status"] == "Serving":
        return 0
    queue=read_df("""SELECT id, priority, created_at FROM tokens
        WHERE status='Waiting' AND date(created_at)=date(?) 
        ORDER BY priority DESC, created_at ASC, id ASC""", (row["created_at"],))
    ids=queue["id"].tolist()
    try:
        position=ids.index(token_id)
    except ValueError:
        return int(row["estimated_minutes"] or 0)
    active=read_df("SELECT COUNT(*) AS n FROM tokens WHERE status='Serving' AND date(created_at)=date(?)", (row["created_at"],))
    active_count=int(active.iloc[0]["n"])
    counters=read_df("SELECT COUNT(*) AS n FROM counters WHERE is_active=1")
    active_counters=max(1,int(counters.iloc[0]["n"]))
    workload=max(0, position + active_count)
    return int(math.ceil((workload / active_counters) * avg))

def refresh_estimates():
    waiting=read_df("SELECT id FROM tokens WHERE status='Waiting'")
    for tid in waiting["id"].tolist():
        est=waiting_estimate(int(tid))
        execute("UPDATE tokens SET estimated_minutes=? WHERE id=?", (est, int(tid)))

def add_token(name, service, priority):
    token_no=next_token_number()
    now=datetime.now().isoformat(timespec="seconds")
    execute("""INSERT INTO tokens(token_no,customer_name,service_type,priority,status,created_at)
               VALUES(?,?,?,?, 'Waiting', ?)""", (token_no,name.strip(),service,int(priority),now))
    refresh_estimates()
    return token_no

def get_queue():
    return read_df("""SELECT t.id,t.token_no,t.customer_name,t.service_type,
        CASE WHEN t.priority=1 THEN 'Priority' ELSE 'Normal' END AS queue_type,
        t.status,t.created_at,t.called_at,t.completed_at,t.estimated_minutes,
        c.name AS counter_name
        FROM tokens t LEFT JOIN counters c ON t.counter_id=c.id
        WHERE date(t.created_at)=date('now','localtime')
        ORDER BY CASE t.status WHEN 'Serving' THEN 0 WHEN 'Waiting' THEN 1 ELSE 2 END,
        t.priority DESC,t.created_at ASC""")

init_db()

st.title("🎟️ QueueWise")
st.caption("Intelligent Queue Prediction and Crowd Flow Management System")
st.info("Demo application: queue records are stored locally in a SQLite database on this computer.")

with st.sidebar:
    st.header("Navigation")
    page=st.radio("Choose a module", ["Overview","Get a Token","Live Queue","Admin Panel","Analytics"])
    st.divider()
    st.caption(f"Average service time: {get_avg_service():.1f} min")
    st.caption("Admin demo PIN: 1234")

if page == "Overview":
    queue=get_queue()
    waiting=int((queue.status=="Waiting").sum()) if not queue.empty else 0
    serving=int((queue.status=="Serving").sum()) if not queue.empty else 0
    completed=int((queue.status=="Completed").sum()) if not queue.empty else 0
    counters=read_df("SELECT * FROM counters")
    active=int(counters.is_active.sum()) if not counters.empty else 0
    a,b,c,d=st.columns(4)
    a.metric("Waiting",waiting)
    b.metric("Currently Serving",serving)
    c.metric("Completed Today",completed)
    d.metric("Active Counters",active)
    st.subheader("How QueueWise works")
    x,y,z=st.columns(3)
    x.markdown("**1. Get a token**\n\nEnter a name and select a service. A unique token is generated.")
    y.markdown("**2. Track your position**\n\nCheck the live queue and estimated waiting time.")
    z.markdown("**3. Serve and analyse**\n\nAdmins call tokens, complete service and review daily statistics.")
    st.subheader("Today's queue")
    if queue.empty:
        st.success("No tokens have been generated today. Start by using Get a Token.")
    else:
        st.dataframe(queue[["token_no","customer_name","service_type","queue_type","status","estimated_minutes","counter_name"]],
                     use_container_width=True, hide_index=True)

elif page == "Get a Token":
    st.subheader("Generate a Queue Token")
    with st.form("token_form", clear_on_submit=True):
        name=st.text_input("Customer / Student name", max_chars=60)
        service=st.selectbox("Select service", ["General Enquiry","Fees / Accounts","Certificate Request","IT Support","Admission Enquiry","Other"])
        priority=st.checkbox("Priority service (use only when authorised)")
        submitted=st.form_submit_button("Generate Token", type="primary")
    if submitted:
        if not name.strip():
            st.error("Please enter a name before generating a token.")
        else:
            token=add_token(name,service,priority)
            st.success(f"Token generated successfully: {token}")
            st.write("Keep this token number to check your queue status.")
            st.metric("Estimated waiting time", f"{waiting_estimate(read_df('SELECT id FROM tokens WHERE token_no=?',(token,)).iloc[0]['id'])} minutes")
    st.caption("Priority tokens are placed ahead of normal waiting tokens. Use priority only for authorised cases.")

elif page == "Live Queue":
    st.subheader("Live Queue Status")
    refresh_estimates()
    queue=get_queue()
    if queue.empty:
        st.info("There are no tokens for today yet.")
    else:
        serving=queue[queue.status=="Serving"]
        waiting=queue[queue.status=="Waiting"]
        done=queue[queue.status=="Completed"]
        st.markdown("#### Now Serving")
        if serving.empty:
            st.info("No token is currently being served.")
        else:
            for _,r in serving.iterrows():
                st.success(f"{r.token_no} — {r.customer_name} | {r.counter_name or 'Counter not assigned'}")
        st.markdown("#### Waiting")
        if waiting.empty:
            st.info("No customers are waiting.")
        else:
            st.dataframe(waiting[["token_no","customer_name","service_type","queue_type","estimated_minutes"]],
                         use_container_width=True,hide_index=True)
        with st.expander(f"Completed today ({len(done)})"):
            st.dataframe(done[["token_no","customer_name","service_type","completed_at"]],use_container_width=True,hide_index=True)

elif page == "Admin Panel":
    st.subheader("Administrator Controls")
    pin=st.text_input("Enter admin PIN", type="password")
    if pin != "1234":
        st.warning("Enter the demo PIN to access queue controls.")
    else:
        st.success("Admin access granted for this local demonstration.")
        counters=read_df("SELECT * FROM counters ORDER BY id")
        st.markdown("#### Counter status")
        for _,counter in counters.iterrows():
            col1,col2,col3=st.columns([2,1,2])
            col1.write(counter["name"])
            col2.write("Active" if counter["is_active"] else "Inactive")
            if col3.button("Deactivate" if counter["is_active"] else "Activate",key=f"toggle_{counter['id']}"):
                execute("UPDATE counters SET is_active=? WHERE id=?", (0 if counter["is_active"] else 1,int(counter["id"])))
                st.rerun()
        st.markdown("#### Queue actions")
        q=read_df("""SELECT id,token_no,customer_name,status FROM tokens
                    WHERE date(created_at)=date('now','localtime') AND status IN ('Waiting','Serving')
                    ORDER BY CASE status WHEN 'Serving' THEN 0 ELSE 1 END,priority DESC,created_at ASC""")
        if q.empty:
            st.info("No active tokens.")
        else:
            labels={int(r.id):f"{r.token_no} — {r.customer_name} ({r.status})" for _,r in q.iterrows()}
            selected=st.selectbox("Select token",list(labels.keys()),format_func=lambda x:labels[x])
            active_counters=read_df("SELECT id,name FROM counters WHERE is_active=1 ORDER BY id")
            if not active_counters.empty:
                counter_map={int(r.id):r.name for _,r in active_counters.iterrows()}
                selected_counter=st.selectbox("Assign counter",list(counter_map.keys()),format_func=lambda x:counter_map[x])
            else:
                selected_counter=None
                st.error("No active counters. Activate at least one counter.")
            row=q[q.id==selected].iloc[0]
            c1,c2=st.columns(2)
            if c1.button("Call / Start Service",disabled=(row.status!="Waiting" or selected_counter is None),type="primary"):
                execute("UPDATE tokens SET status='Serving',counter_id=?,called_at=? WHERE id=?",
                        (selected_counter,datetime.now().isoformat(timespec="seconds"),selected))
                refresh_estimates()
                st.success("Token moved to Serving.")
                st.rerun()
            if c2.button("Complete Service",disabled=(row.status!="Serving")):
                token=read_df("SELECT called_at FROM tokens WHERE id=?",(selected,))
                start=pd.to_datetime(token.iloc[0]["called_at"])
                duration=max(1.0,(datetime.now()-start.to_pydatetime()).total_seconds()/60)
                execute("UPDATE tokens SET status='Completed',completed_at=? WHERE id=?",
                        (datetime.now().isoformat(timespec="seconds"),selected))
                execute("INSERT INTO service_times(token_id,duration_minutes,service_date) VALUES(?,?,?)",
                        (selected,duration,date.today().isoformat()))
                refresh_estimates()
                st.success(f"Service completed. Recorded duration: {duration:.1f} minutes.")
                st.rerun()
        st.markdown("#### Add a service counter")
        new_counter=st.text_input("Counter name",placeholder="Example: Counter 4")
        if st.button("Add Counter"):
            if new_counter.strip():
                try:
                    execute("INSERT INTO counters(name,is_active) VALUES(?,1)",(new_counter.strip(),))
                    st.success("Counter added.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("A counter with that name already exists.")
        st.caption("For a real deployment, replace the demo PIN with secure authentication and role-based access.")

elif page == "Analytics":
    st.subheader("Queue Analytics")
    allq=read_df("""SELECT token_no,customer_name,service_type,priority,status,created_at,called_at,completed_at
                    FROM tokens ORDER BY created_at DESC""")
    if allq.empty:
        st.info("Analytics will appear after tokens have been generated.")
    else:
        allq["service_date"]=pd.to_datetime(allq.created_at).dt.date
        total=len(allq)
        completed=int((allq.status=="Completed").sum())
        waiting=int((allq.status=="Waiting").sum())
        serving=int((allq.status=="Serving").sum())
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Total Tokens",total)
        m2.metric("Completed",completed)
        m3.metric("Waiting",waiting)
        m4.metric("Serving",serving)
        status_counts=allq.status.value_counts().rename_axis("Status").reset_index(name="Count")
        st.plotly_chart(px.pie(status_counts,names="Status",values="Count",title="Token Status Distribution"),use_container_width=True)
        service_counts=allq.service_type.value_counts().rename_axis("Service").reset_index(name="Tokens")
        st.plotly_chart(px.bar(service_counts,x="Service",y="Tokens",title="Requests by Service"),use_container_width=True)
        times=read_df("SELECT duration_minutes,service_date FROM service_times")
        if not times.empty:
            st.metric("Average completed service time",f"{times.duration_minutes.mean():.1f} minutes")
            st.plotly_chart(px.line(times,x="service_date",y="duration_minutes",title="Recorded Service Duration"),use_container_width=True)
        st.download_button("Download token report (CSV)",allq.to_csv(index=False).encode("utf-8"),
                           file_name="queuewise_token_report.csv",mime="text/csv")
        st.download_button("Download service-time report (CSV)",times.to_csv(index=False).encode("utf-8"),
                           file_name="queuewise_service_times.csv",mime="text/csv")
