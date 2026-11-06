import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta
import os
from supabase import create_client, Client

# --- SUPABASE DATABASE INITIALIZATION ---
@st.cache_resource
def init_supabase() -> Client:
    def load_data(file_path):
    table_name = file_path.replace(".csv", "")
    # Try loading from Supabase Cloud first
    if supabase:
        try:
            res = supabase.table(table_name).select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.date
                return df
        except Exception:
            pass
            
    # Fallback to local CSV if offline/local
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)

supabase = init_supabase()

# --- FILE PATH SETUP ---
MORNING_LOG = "morning_logs.csv"
EVENING_LOG = "evening_logs.csv"
SLEEP_LOG = "sleep_logs.csv"

# --- HELPER FUNCTIONS ---
def load_data(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_data(df, file_path):
    df_to_save = df.copy()
    if "date" in df_to_save.columns:
        df_to_save["date"] = df_to_save["date"].astype(str)
    df_to_save.to_csv(file_path, index=False)

def check_entry_exists(file_path, check_date):
    df = load_data(file_path)
    if not df.empty and "date" in df.columns:
        return check_date in df["date"].values
    return False

# --- APP CONFIGURATION ---
st.set_page_config(page_title="My Personal Health OS", layout="wide", page_icon="🛡️")

# --- INITIALIZE SESSION STATE ---
if "edit_morning" not in st.session_state:
    st.session_state["edit_morning"] = False
if "edit_evening" not in st.session_state:
    st.session_state["edit_evening"] = False
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "☀️ Morning"
if "num_workouts" not in st.session_state:
    st.session_state["num_workouts"] = 1

st.title("🛡️ My Personal Health OS")

# ==========================================
# MOBILE STACKED NAVIGATION BOXES
# ==========================================
st.markdown("### 📱 Navigation")

nav_col1, nav_col2 = st.columns(2)

with nav_col1:
    if st.button("☀️ Morning Log", use_container_width=True, type="primary" if st.session_state["active_tab"] == "☀️ Morning" else "secondary"):
        st.session_state["active_tab"] = "☀️ Morning"
        st.rerun()

    if st.button("📥 Sleep Import", use_container_width=True, type="primary" if st.session_state["active_tab"] == "📥 Sleep Import" else "secondary"):
        st.session_state["active_tab"] = "📥 Sleep Import"
        st.rerun()

with nav_col2:
    if st.button("🌙 Evening Log", use_container_width=True, type="primary" if st.session_state["active_tab"] == "🌙 Evening" else "secondary"):
        st.session_state["active_tab"] = "🌙 Evening"
        st.rerun()

    if st.button("📊 Dashboard", use_container_width=True, type="primary" if st.session_state["active_tab"] == "📊 Dashboard" else "secondary"):
        st.session_state["active_tab"] = "📊 Dashboard"
        st.rerun()

st.divider()

# ==========================================
# PAGE 1: MORNING LOG (PVT WITH LAPSES & FALSE STARTS)
# ==========================================
if st.session_state["active_tab"] == "☀️ Morning":
    st.header("Morning Check-In")
    
    today_date = date.today()
    already_logged_morning = check_entry_exists(MORNING_LOG, today_date)

    if already_logged_morning and not st.session_state["edit_morning"]:
        st.warning(f"🔒 Morning entry for **{today_date.strftime('%Y-%m-%d')}** has already been recorded!")
        if st.button("✏️ Edit / Retake Today's Morning Entry", use_container_width=True):
            st.session_state["edit_morning"] = True
            st.rerun()
    else:
        if st.session_state["edit_morning"]:
            st.info("⚠️ **Edit Mode Active:** Submitting will update today's log.")

        st.subheader("⏱️ Cognitive Focus Test (PVT)")
        st.caption("Tap 'Start Test', wait for the box to turn GREEN, then tap as fast as you can. Avoid false starts!")

        pvt_js_component = """
        <div id="pvt-container" style="text-align: center; font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 12px; border: 2px solid #444; border-radius: 12px; background-color: #121212; color: white;">
            <div id="box" style="width: 100%; height: 180px; background-color: #2b2b2b; border-radius: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; cursor: pointer; user-select: none; margin-bottom: 12px; -webkit-tap-highlight-color: transparent;">
                <span>Tap to Start 60s PVT</span>
            </div>
            <button id="start-btn" style="width: 100%; padding: 14px; font-size: 18px; font-weight: bold; cursor: pointer; border-radius: 8px; border: none; background-color: #28a745; color: white;">Start 60s Test</button>
            <p id="status" style="margin-top: 10px; font-size: 14px; color: #aaa;">Status: Ready</p>
        </div>

        <script>
            let box = document.getElementById("box");
            let startBtn = document.getElementById("start-btn");
            let status = document.getElementById("status");

            let times = [];
            let falseStarts = 0;
            let testActive = false;
            let waitingForGreen = false;
            let startTime, timeoutId, testTimerId;
            let duration = 60000;

            function getRandomDelay() {
                return Math.floor(Math.random() * 3000) + 2000;
            }

            function startTest() {
                times = [];
                falseStarts = 0;
                testActive = true;
                startBtn.disabled = true;
                startBtn.style.opacity = "0.4";
                status.innerText = "Test running... Tap when GREEN!";
                nextTrial();
                testTimerId = setTimeout(endTest, duration);
            }

            function nextTrial() {
                if (!testActive) return;
                box.style.backgroundColor = "#dc3545";
                box.innerHTML = "<span>WAIT FOR GREEN...</span>";
                waitingForGreen = false;

                let delay = getRandomDelay();
                timeoutId = setTimeout(() => {
                    if (!testActive) return;
                    box.style.backgroundColor = "#28a745";
                    box.innerHTML = "<span>TAP NOW!</span>";
                    startTime = Date.now();
                    waitingForGreen = true;
                }, delay);
            }

            box.addEventListener("pointerdown", (e) => {
                e.preventDefault();
                if (!testActive) return;

                if (waitingForGreen) {
                    let reactionTime = Date.now() - startTime;
                    times.push(reactionTime);
                    waitingForGreen = false;
                    box.style.backgroundColor = "#2b2b2b";
                    box.innerHTML = "<span>" + reactionTime + " ms</span>";
                    setTimeout(nextTrial, 800);
                } else if (box.innerHTML.includes("WAIT FOR GREEN...")) {
                    clearTimeout(timeoutId);
                    falseStarts++;
                    box.innerHTML = "<span>FALSE START!</span>";
                    box.style.backgroundColor = "#ffc107";
                    box.style.color = "#000";
                    setTimeout(() => {
                        box.style.color = "#fff";
                        nextTrial();
                    }, 1200);
                }
            });

            function endTest() {
                testActive = false;
                clearTimeout(timeoutId);
                box.style.backgroundColor = "#2b2b2b";
                startBtn.disabled = false;
                startBtn.style.opacity = "1";

                if (times.length === 0) {
                    box.innerHTML = "<span>No Taps Recorded</span>";
                    status.innerText = "Test finished without inputs.";
                    return;
                }

                let lapses = times.filter(t => t > 500).length;
                times.sort((a, b) => a - b);
                let median = Math.round(times[Math.floor(times.length / 2)]);
                
                box.innerHTML = "<span style='font-size:20px;'>" + median + " ms</span><span style='font-size:14px; font-weight:normal; color:#ccc; margin-top:4px;'>Lapses: " + lapses + " | False Starts: " + falseStarts + "</span>";
                status.innerText = "Done! Median: " + median + "ms (Copied median to clipboard!)";

                navigator.clipboard.writeText(median.toString()).catch(err => console.log('Clipboard copy failed', err));
            }

            startBtn.addEventListener("click", startTest);
        </script>
        """
        st.components.v1.html(pvt_js_component, height=290)

        st.divider()

        with st.form("morning_form"):
            log_date = st.date_input("Date", today_date)
            pvt_reaction_time = st.number_input("PVT Median Reaction Time (ms)", min_value=100, max_value=1500, value=250, help="Paste your PVT median score here")
            pvt_lapses = st.number_input("PVT Lapses (>500ms)", min_value=0, value=0, step=1, help="Number of responses slower than 500ms")
            pvt_false_starts = st.number_input("PVT False Starts", min_value=0, value=0, step=1, help="Number of early taps before green")
            
            st.markdown("#### Physical & Mental Readiness")
            soreness = st.slider("Body Soreness (1-10)", 1, 10, 1)
            stress_level = st.slider("Daily Stress Level (1-10)", 1, 10, 3)

            submit_morning = st.form_submit_button("💾 Save Morning Log", use_container_width=True, type="primary")

            if submit_morning:
                new_entry = {
                    "date": log_date,
                    "pvt_reaction_time": pvt_reaction_time,
                    "pvt_lapses": pvt_lapses,
                    "pvt_false_starts": pvt_false_starts,
                    "soreness": soreness,
                    "stress_level": stress_level
                }
                df_m = load_data(MORNING_LOG)
                if not df_m.empty and "date" in df_m.columns:
                    df_m = df_m[df_m["date"] != log_date]
                df_m = pd.concat([df_m, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(df_m, MORNING_LOG)
                
                st.session_state["edit_morning"] = False
                st.success("Morning log saved successfully!")
                st.rerun()

# ==========================================
# PAGE 2: EVENING LOG (DYNAMIC WORKOUT MENU)
# ==========================================
elif st.session_state["active_tab"] == "🌙 Evening":
    st.header("Evening Check-In")

    now = datetime.now()
    default_date = date.today() - timedelta(days=1) if now.hour < 4 else date.today()
    already_logged_evening = check_entry_exists(EVENING_LOG, default_date)

    if already_logged_evening and not st.session_state["edit_evening"]:
        st.warning(f"🔒 Evening entry for **{default_date.strftime('%Y-%m-%d')}** has already been recorded!")
        if st.button("✏️ Edit Evening Entry", use_container_width=True):
            st.session_state["edit_evening"] = True
            st.rerun()
    else:
        if st.session_state["edit_evening"]:
            st.info("⚠️ **Edit Mode Active:** Submitting will update this log.")

        log_date = st.date_input("Log Date", default_date)
        weight = st.number_input("Weight (lbs)", min_value=50.0, max_value=500.0, value=170.0, step=0.5)
        
        st.markdown("---")
        st.subheader("🏋️ Workout Menu")
        
        workouts_data = []
        
        # Dynamically create workout blocks
        for i in range(st.session_state["num_workouts"]):
            st.markdown(f"#### Workout {i+1}")
            w_type = st.selectbox(
                "Workout Type", 
                ["Rest Day", "Calisthenics", "Run", "Swim", "Bike", "Weight Training", "HIIT / Circuit", "Other"],
                key=f"type_{i}"
            )
            
            w_data = {"type": w_type}
            
            if w_type == "Calisthenics":
                c1, c2 = st.columns(2)
                with c1:
                    w_data["pushups"] = st.number_input("Push-ups", min_value=0, step=5, key=f"push_{i}")
                    w_data["curlups"] = st.number_input("Curl-ups", min_value=0, step=1, key=f"curl_{i}")
                with c2:
                    w_data["pullups"] = st.number_input("Pull-ups", min_value=0, step=1, key=f"pull_{i}")
                    w_data["situps"] = st.number_input("Sit-ups", min_value=0, step=5, key=f"sit_{i}")
                    
            elif w_type in ["Run", "Swim", "Bike"]:
                c1, c2 = st.columns(2)
                with c1:
                    w_data["duration"] = st.text_input("Duration (e.g., 45 mins)", key=f"dur_{i}")
                with c2:
                    w_data["distance"] = st.text_input("Distance (e.g., 3 miles, 2000m)", key=f"dist_{i}")
                    
            elif w_type in ["Weight Training", "HIIT / Circuit", "Other"]:
                w_data["custom_workout"] = st.text_input("Details / Notes", placeholder="e.g., Back and Biceps", key=f"cust_{i}")
            
            workouts_data.append(w_data)
        
        # Add another workout button
        if st.button("➕ Add Another Workout"):
            st.session_state["num_workouts"] += 1
            st.rerun()

        st.markdown("---")
        
        # Save Button (Outside form to allow real-time UI changes)
        submit_evening = st.button("💾 Save Evening Log", use_container_width=True, type="primary")

        if submit_evening:
            # Aggregate all entered workouts behind the scenes for the CSV
            pushups = pullups = curlups = situps = 0
            final_types, final_durs, final_dists, final_customs = [], [], [], []
            
            for w in workouts_data:
                t = w["type"]
                if t != "Rest Day":
                    final_types.append(t)
                
                if t == "Calisthenics":
                    pushups += w.get("pushups", 0)
                    curlups += w.get("curlups", 0)
                    pullups += w.get("pullups", 0)
                    situps += w.get("situps", 0)
                elif t in ["Run", "Swim", "Bike"]:
                    if w.get("duration"): final_durs.append(f"{t}: {w['duration']}")
                    if w.get("distance"): final_dists.append(f"{t}: {w['distance']}")
                elif t in ["Weight Training", "HIIT / Circuit", "Other"]:
                    if w.get("custom_workout"): final_customs.append(f"{t}: {w['custom_workout']}")

            if not final_types:
                final_types = ["Rest Day"]

            new_entry = {
                "date": log_date,
                "weight": weight,
                "workout_type": ", ".join(final_types),
                "pushups": pushups,
                "pullups": pullups,
                "curlups": curlups,
                "situps": situps,
                "duration": " | ".join(final_durs),
                "distance": " | ".join(final_dists),
                "custom_workout": " | ".join(final_customs)
            }
            
            df_e = load_data(EVENING_LOG)
            if not df_e.empty and "date" in df_e.columns:
                df_e = df_e[df_e["date"] != log_date]
            df_e = pd.concat([df_e, pd.DataFrame([new_entry])], ignore_index=True)
            save_data(df_e, EVENING_LOG)

            st.session_state["edit_evening"] = False
            st.session_state["num_workouts"] = 1  # Reset to 1 workout slot after successful save
            st.success("Evening log saved successfully!")
            st.rerun()

# ==========================================
# PAGE 3: SLEEP FILE PARSER & SAVER
# ==========================================
elif st.session_state["active_tab"] == "📥 Sleep Import":
    st.header("📥 Import External Sleep Data")
    st.markdown("Upload a CSV file exported from **Sleep Cycle**, **Apple Health**, or **Oura**.")

    uploaded_file = st.file_uploader("Choose CSV File", type=["csv"])

    if uploaded_file is not None:
        try:
            sleep_df = pd.read_csv(uploaded_file, sep=None, engine='python')
            st.subheader("Data Preview")
            st.dataframe(sleep_df.head(), use_container_width=True)

            if "Start" in sleep_df.columns and "End" in sleep_df.columns:
                sleep_df["Start"] = pd.to_datetime(sleep_df["Start"])
                sleep_df["End"] = pd.to_datetime(sleep_df["End"])
                
                # Use the end date (morning) as the unified date for logs
                sleep_df["date"] = sleep_df["End"].dt.date
                
                if "Time in bed (seconds)" in sleep_df.columns:
                    sleep_df["sleep_hours"] = (sleep_df["Time in bed (seconds)"] / 3600).round(2)
                else:
                    sleep_df["sleep_hours"] = ((sleep_df["End"] - sleep_df["Start"]).dt.total_seconds() / 3600).round(2)

                if "Sleep quality" in sleep_df.columns:
                    sleep_df["sleep_quality"] = (
                        sleep_df["Sleep quality"].astype(str).str.rstrip("%").astype(float) / 10
                    ).round(1)

                st.success("Sleep Cycle format detected and successfully parsed!")

                latest_row = sleep_df.iloc[-1]
                st.metric("Latest Sleep Duration", f"{latest_row['sleep_hours']} hrs")
                if "sleep_quality" in sleep_df.columns:
                    st.metric("Latest Sleep Quality Score", f"{latest_row['sleep_quality']}/10")
                
                if st.button("💾 Save Extracted Sleep Data to Logs", type="primary", use_container_width=True):
                    # Filter columns to save
                    cols_to_save = ["date", "sleep_hours"]
                    if "sleep_quality" in sleep_df.columns:
                        cols_to_save.append("sleep_quality")
                    
                    df_to_save = sleep_df[cols_to_save].copy()
                    
                    # Merge with existing, overwriting duplicates based on date
                    df_existing = load_data(SLEEP_LOG)
                    if not df_existing.empty:
                        df_existing["date"] = pd.to_datetime(df_existing["date"]).dt.date
                        # Combine and drop duplicates keeping the newly imported data (last)
                        combined = pd.concat([df_existing, df_to_save]).drop_duplicates(subset=["date"], keep="last")
                    else:
                        combined = df_to_save
                        
                    save_data(combined, SLEEP_LOG)
                    st.success(f"Successfully saved {len(df_to_save)} sleep records!")

            else:
                st.warning("Custom CSV uploaded. Standard sleep fields could not be auto-mapped.")

        except Exception as e:
            st.error(f"Error reading file: {e}")

# ==========================================
# PAGE 4: DASHBOARD ANALYTICS
# ==========================================
elif st.session_state["active_tab"] == "📊 Dashboard":
    st.header("📊 Health & Performance Analytics")
    
    df_m = load_data(MORNING_LOG)
    df_e = load_data(EVENING_LOG)
    df_s = load_data(SLEEP_LOG)

    if df_m.empty and df_e.empty and df_s.empty:
        st.info("No data logged yet. Start entering daily logs or import sleep data to generate charts.")
    else:
        # Pre-process dates
        if not df_m.empty: df_m["date"] = pd.to_datetime(df_m["date"])
        if not df_e.empty: df_e["date"] = pd.to_datetime(df_e["date"])
        if not df_s.empty: df_s["date"] = pd.to_datetime(df_s["date"])

        # 1. PVT COGNITIVE TRENDS
        if not df_m.empty and "pvt_reaction_time" in df_m.columns:
            st.subheader("⚡ Cognitive Focus: PVT Reaction Time")
            df_m = df_m.sort_values("date").reset_index(drop=True)
            df_m["7d_avg"] = df_m["pvt_reaction_time"].rolling(window=7, min_periods=1).mean()
            df_m["30d_avg"] = df_m["pvt_reaction_time"].rolling(window=30, min_periods=1).mean()

            fig_pvt = go.Figure()
            fig_pvt.add_trace(go.Scatter(x=df_m["date"], y=df_m["pvt_reaction_time"], mode="markers+lines", name="Daily Raw (ms)", line=dict(color="#4da6ff")))
            fig_pvt.add_trace(go.Scatter(x=df_m["date"], y=df_m["7d_avg"], mode="lines", name="7-Day Avg", line=dict(color="#ff9900", width=2)))
            fig_pvt.add_trace(go.Scatter(x=df_m["date"], y=df_m["30d_avg"], mode="lines", name="30-Day Avg", line=dict(color="#ff3333", width=2, dash="dash")))

            fig_pvt.update_layout(
                title="Reaction Time (Lower is Better)",
                xaxis_title="Date",
                yaxis_title="ms",
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_pvt, use_container_width=True)

        # 2. SLEEP TRENDS & QUALITY
        if not df_s.empty and "sleep_hours" in df_s.columns:
            st.subheader("🛌 Sleep Duration & Quality")
            df_s = df_s.sort_values("date").reset_index(drop=True)
            
            fig_sleep = make_subplots(specs=[[{"secondary_y": True}]])
            fig_sleep.add_trace(
                go.Bar(x=df_s["date"], y=df_s["sleep_hours"], name="Sleep Hours", marker_color="#8b5cf6", opacity=0.7),
                secondary_y=False,
            )
            if "sleep_quality" in df_s.columns:
                fig_sleep.add_trace(
                    go.Scatter(x=df_s["date"], y=df_s["sleep_quality"], name="Sleep Quality (0-10)", mode="lines+markers", line=dict(color="#2dd4bf", width=3)),
                    secondary_y=True,
                )
                
            fig_sleep.update_layout(
                title="Nightly Sleep Trends",
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_sleep.update_yaxes(title_text="Hours", secondary_y=False)
            if "sleep_quality" in df_s.columns:
                fig_sleep.update_yaxes(title_text="Quality Score", range=[0, 10], secondary_y=True)
                
            st.plotly_chart(fig_sleep, use_container_width=True)

        # 3. SLEEP VS. PVT CORRELATION
        if not df_m.empty and not df_s.empty and "pvt_reaction_time" in df_m.columns:
            merged_sleep_pvt = pd.merge(df_m, df_s, on="date", how="inner")
            if not merged_sleep_pvt.empty:
                st.subheader("🧠 Sleep Duration vs. Cognitive Focus (PVT)")
                fig_corr = px.scatter(
                    merged_sleep_pvt, 
                    x="sleep_hours", 
                    y="pvt_reaction_time", 
                    trendline="ols",
                    title="How Sleep Hours Affect Reaction Time",
                    labels={"sleep_hours": "Sleep Hours", "pvt_reaction_time": "Reaction Time (ms)"}
                )
                fig_corr.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_corr, use_container_width=True)

        # 4. CALISTHENICS REPETITION VOLUME
        if not df_e.empty and any(c in df_e.columns for c in ["pushups", "pullups", "chinups", "curlups", "situps"]):
            st.subheader("💪 Calisthenics Volume")
            df_e = df_e.sort_values("date").reset_index(drop=True)
            fig_cal = go.Figure()
            if "pushups" in df_e.columns: fig_cal.add_trace(go.Bar(x=df_e["date"], y=df_e["pushups"], name="Push-ups"))
            if "pullups" in df_e.columns: fig_cal.add_trace(go.Bar(x=df_e["date"], y=df_e["pullups"], name="Pull-ups"))
            if "curlups" in df_e.columns: fig_cal.add_trace(go.Bar(x=df_e["date"], y=df_e["curlups"], name="Curl-ups"))
            if "situps" in df_e.columns: fig_cal.add_trace(go.Bar(x=df_e["date"], y=df_e["situps"], name="Sit-ups"))

            fig_cal.update_layout(
                barmode="stack",
                title="Daily Calisthenic Reps",
                xaxis_title="Date",
                yaxis_title="Reps",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_cal, use_container_width=True)

        # 5. WEIGHT TRACKING (FROM EVENING LOG)
        if not df_e.empty and "weight" in df_e.columns:
            st.subheader("⚖️ Weight Progression")
            fig_weight = px.line(df_e, x="date", y="weight", markers=True, title="Body Weight (lbs)")
            fig_weight.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_weight, use_container_width=True)

        # 6. RECOVERY VS. STRESS CORRELATION
        if not df_m.empty and "soreness" in df_m.columns and "stress_level" in df_m.columns:
            st.subheader("🧘 Stress vs. Soreness Tracker")
            fig_rec = go.Figure()
            fig_rec.add_trace(go.Scatter(x=df_m["date"], y=df_m["soreness"], name="Morning Soreness", line=dict(color="#a855f7")))
            fig_rec.add_trace(go.Scatter(x=df_m["date"], y=df_m["stress_level"], name="Morning Stress", line=dict(color="#f97316")))
             fig_rec.update_layout(
                title="Soreness vs. Stress Levels",
                xaxis_title="Date",
                yaxis_title="Scale (1-10)",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_rec, use_container_width=True)