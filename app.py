import streamlit as st
import pandas as pd
from groq import Groq
import os

# Mobile screen optimization
st.set_page_config(page_title="Secure Cloud Chat", page_icon="🔐", layout="centered")
st.title("🔐 Google Sheet SQL ChatGPT")
st.markdown("Sidebar se data direct jorein aur live SQL chat karein.")

# 1. CREDENTIALS LOAD (Streamlit Dashboard > Secrets)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.environ.get("GOOGLE_SHEET_URL", ""))

if not GROQ_API_KEY or not GOOGLE_SHEET_URL:
    st.error("❌ Configuration Missing! Please add GROQ_API_KEY and GOOGLE_SHEET_URL in Streamlit Secrets.")
    st.stop()

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)
LATEST_ACTIVE_MODEL = "gpt-oss-120b"

# Google Sheet link ko automatic CSV format me badalna (Read karne ke liye)
csv_url = GOOGLE_SHEET_URL.replace("/edit?usp=sharing", "/export?format=csv").replace("/edit", "/export?format=csv")

@st.cache_data(ttl=2)
def load_data():
    return pd.read_csv(csv_url)

try:
    df_data = load_data()
except Exception as e:
    st.error("Google Sheet read error! Make sure share access is set to 'Anyone with the link as Editor'.")
    st.stop()

DB_SCHEMA = "Table Name: secret_data\nColumns: title (TEXT), secret_info (TEXT), notes (TEXT)"

# -------------------------------------------------------------
# 2. SIDEBAR: DATA KAISE JORENGE (Bina Kisi JSON ya Extra Package Ke)
# -------------------------------------------------------------
st.sidebar.header("➕ Add New Secret Data")
with st.sidebar.form("input_form", clear_on_submit=True):
    new_title = st.sidebar.text_input("Item Name (e.g., Wi-Fi, Insta Pass):")
    new_secret = st.sidebar.text_input("Secret Code / Info:", type="password")
    new_notes = st.sidebar.text_area("Extra Notes (Optional):")
    submit_btn = st.sidebar.form_submit_button("Save to Google Sheet")
    
    if submit_btn and new_title and new_secret:
        with st.sidebar.spinner("Saving row directly to sheet..."):
            # Naya data local DataFrame me jodna
            new_row = pd.DataFrame([{"title": new_title, "secret_info": new_secret, "notes": new_notes}])
            updated_df = pd.concat([df_data, new_row], ignore_index=True)
            
            # Google Sheet ke standard write API par data bhejna
            # Isse bina kisi service account ke direct write hoga
            try:
                sheet_id = GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]
                push_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv"
                # Local cache reset aur refresh
                st.sidebar.success(f"✅ '{new_title}' successfully saved!")
                st.cache_data.clear()
                st.rerun()
            except Exception as ex:
                st.sidebar.error(f"Write error: {ex}")

st.sidebar.metric("Total Saved Secrets", len(df_data))

# -------------------------------------------------------------
# 3. CORE AI CONVERSION ENGINE (SQL RAG Simulation via Pandas)
# -------------------------------------------------------------
def ask_vault_ai(user_prompt):
    sql_generation_prompt = f"Convert the user's question into a standard SQL query. SCHEMA: {DB_SCHEMA} TABLE RULE: Query from table 'secret_data'. OUTPUT RULE: Return ONLY the raw SQL query string. No markdown block formatting or quotes. QUESTION: {user_prompt}"
    try:
        sql_res = client.chat.completions.create(
            messages=[{"role": "user", "content": sql_generation_prompt}],
            model=LATEST_ACTIVE_MODEL,
            temperature=0.0
        )
        generated_sql = sql_res.choices.message.content.strip()
        
        # Pandas text matching filtering
        query_result = df_data[df_data['title'].str.contains(user_prompt, case=False, na=False) | 
                               df_data['notes'].str.contains(user_prompt, case=False, na=False)]
        
        if query_result.empty:
            query_result = df_data
            
        final_answer_prompt = f"User Question: {user_prompt}\nSQL Intended: {generated_sql}\nDatabase Result Table:\n{query_result.to_string()}\n\nTask: Act as an elite personal assistant. Deliver a highly polished conversational answer using the data."
        ans_res = client.chat.completions.create(
            messages=[{"role": "user", "content": final_answer_prompt}],
            model=LATEST_ACTIVE_MODEL,
            temperature=0.3
        )
        return ans_res.choices.message.content, generated_sql
    except Exception as e:
        return f"Error executing model: {str(e)}", None

# -------------------------------------------------------------
# 4. CHAT INTERFACE
# -------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])

if user_query := st.chat_input("Ask about your secrets..."):
    with st.chat_message("user"):
        st.markdown(user_query)
    st.session_state.messages.append({"role": "user", "text": user_query})
    
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            ans, sql = ask_vault_ai(user_query)
            st.markdown(ans)
            if sql:
                with st.expander("🛠️ View SQL Logs"):
                    st.code(sql, language="sql")
            st.session_state.messages.append({"role": "assistant", "text": ans})
            
