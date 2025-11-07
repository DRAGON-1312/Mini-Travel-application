from __future__ import annotations
from typing import List, Dict, Any, Optional

import os, json, time
from collections import deque
from datetime import datetime, timezone, date, timedelta

import requests
import streamlit as st

# Firebase
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore

# Page & global configuration
st.set_page_config(
    page_title="Mini-travel (Streamlit + Firebase + Ollama)",
    page_icon="🧭",
    layout="centered",
)

# Ollama HTTP endpoint (ưu tiên BASE https)
BASE = (
    st.secrets.get("OLLAMA_BASE")
    or os.getenv("OLLAMA_BASE")
    or st.secrets.get("OLLAMA_HOST")
    or os.getenv("OLLAMA_HOST")
    or "http://localhost:11434"
).rstrip("/")

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
DEFAULT_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_S", "300"))
DEFAULT_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "-1")) # -1 = không giới hạn (đến EOS)

# LLM backend selector (default: ollama)
BACKEND = st.secrets.get("LLM_BACKEND") or os.getenv("LLM_BACKEND", "ollama") # "ollama" | "openai" | "gemini"

# OpenAI
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
OPENAI_BASE = st.secrets.get("OPENAI_BASE") or os.getenv("OPENAI_BASE")
OPENAI_MODEL = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Gemini
GEMINI_API_KEY = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = st.secrets.get("GEMINI_MODEL") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Session HTTP dùng lại kết nối
_http = requests.Session()

# Ollama helpers (HTTP)
def ping_ollama(base: str) -> tuple[bool, Optional[str]]:
    """Kiểm tra /api/tags để biết server còn sống."""
    try:
        r = _http.get(f"{base}/api/tags", timeout=8)
        r.raise_for_status()
        _ = r.json()
        return True, None
    except Exception as e:
        return False, str(e)


def list_models(base: str, fallback: str) -> List[str]:
    """Trả danh sách models qua /api/tags (ổn định với ngrok/pinggy)."""
    try:
        r = _http.get(f"{base}/api/tags", timeout=10)
        r.raise_for_status()
        data = r.json() or {}
        models = [m.get("name") or m.get("model") for m in data.get("models", [])]
        return models or [fallback]
    except Exception:
        return [fallback]


def call_ollama_chat(
    base: str,
    messages: List[Dict[str, str]],
    model: str,
    want_json: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    num_predict: int = DEFAULT_NUM_PREDICT,
) -> Dict[str, Any]:
    options = {"temperature": 0.2}
    # chỉ add num_predict nếu >= 0; nếu -1 thì để Ollama chạy tới EOS
    if isinstance(num_predict, int) and num_predict >= 0:
        options["num_predict"] = num_predict
        
    payload = {
        "model": model,
        "messages": messages,
        # stream luôn khi muốn JSON để tránh timeout và cắt cụt
        "stream": bool(want_json),
        "options": options,
    }
    if want_json:
        payload["format"] = "json"

    # nếu stream
    if payload["stream"]:
        with _http.post(f"{base}/api/chat", json=payload, timeout=(10, timeout+120), stream=True) as resp:
            resp.raise_for_status()
            full = ""
            for raw in resp.iter_lines(chunk_size=8192):  # bỏ decode_unicode, tự decode thủ công
                if not raw:
                    continue
                line = raw.decode(resp.encoding or "utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)

                if line.startswith("data:"):
                    line = line[5:].strip()

                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                part = (chunk.get("message") or {}).get("content") or chunk.get("response", "")
                if part:
                    full += part
        return {"message": {"content": full}}

    # còn không thì non-stream như cũ
    r = _http.post(f"{base}/api/chat", json=payload, timeout=(10, timeout))
    r.raise_for_status()
    return r.json()


def extract_content(resp_json: Dict[str, Any]) -> str:
    """Ollama có thể trả {"message":{"content":...}} hoặc {"response":...}"""
    return (resp_json.get("message") or {}).get("content") or resp_json.get("response", "")

# OpenAI wrapper 
def call_openai_chat(
    messages: List[Dict[str, str]],
    model: str,
    want_json: bool = False,
    num_predict: int = 256,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("Missing dependency: pip install openai")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for BACKEND=openai")

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE) if OPENAI_BASE else OpenAI(api_key=OPENAI_API_KEY)
    
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": num_predict,
    }
    if want_json:
        kwargs["response_format"] = {"type": "json_object"}

    r = client.chat.completions.create(**kwargs)
    text = (r.choices[0].message.content or "").strip()
    return {"message": {"content": text}}

# Gemini wrapper
def call_gemini_chat(
    messages: List[Dict[str, str]],
    model: str,
    want_json: bool = False,
    num_predict: int = 256,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("Missing dependency: pip install google-generativeai")

    if not GEMINI_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is required for BACKEND=gemini")

    genai.configure(api_key=GEMINI_API_KEY)
    gmodel = genai.GenerativeModel(model)

    # Gộp history kiểu ChatML (đủ cho LAB)
    prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

    resp = gmodel.generate_content(
        prompt,
        generation_config={"temperature": temperature, "max_output_tokens": num_predict},
    )
    text = (getattr(resp, "text", None) or "").strip()
    # (tuỳ chọn) nếu muốn ép JSON, bạn có thể strip code fences tại đây
    return {"message": {"content": text}}


def chat_backend(
    messages: List[Dict[str, str]],
    model: str,
    want_json: bool,
    num_predict: int,
    temperature: float = 0.2,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    # chuẩn hoá cap
    cap = None if (num_predict is None or int(num_predict) < 0) else int(num_predict)
    if BACKEND == "ollama":
        return call_ollama_chat(BASE, messages, model, want_json, timeout=timeout, num_predict=(cap if cap is not None else -1))
    elif BACKEND == "openai":
        return call_openai_chat(messages, model or OPENAI_MODEL, want_json, (cap if cap is not None else 512), temperature)
    elif BACKEND == "gemini":
        return call_gemini_chat(messages, model or GEMINI_MODEL, want_json, (cap if cap is not None else 512), temperature)
    else:
        raise ValueError(f"Unsupported BACKEND: {BACKEND}")
    
    
# List model theo backend để fill dropdown
def list_models_backend(fallback: str) -> list[str]:
    if BACKEND == "ollama":
        return list_models(BASE, fallback)
    elif BACKEND == "openai":
        return [OPENAI_MODEL]
    elif BACKEND == "gemini":
        return [GEMINI_MODEL]
    return [fallback]

# Firebase clients (Auth + Firestore)
@st.cache_resource
def get_firebase_clients():
    # Pyrebase (Auth)
    firebase_cfg = st.secrets["firebase_client"]
    firebase_app = pyrebase.initialize_app(firebase_cfg)
    auth = firebase_app.auth()

    # Admin (Firestore)
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase_admin"]))
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    return auth, db

try:
    auth, db = get_firebase_clients()
except Exception as e:
    auth = db = None
    st.error("Firebase is not configured (secrets missing).")


# Firestore message helpers
def save_message(uid: str, role: str, content: str):
    doc = {"role": role, "content": content, "ts": datetime.now(timezone.utc)}
    db.collection("chats").document(uid).collection("messages").add(doc)


def load_last_messages(uid: str, limit: int = 16) -> List[Dict[str, str]]:
    q = (
        db.collection("chats")
        .document(uid)
        .collection("messages")
        .order_by("ts", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    docs = list(q.stream())
    docs.reverse()
    out: List[Dict[str, str]] = []
    for d in docs:
        data = d.to_dict() or {}
        out.append({"role": data.get("role", "assistant"), "content": data.get("content", "")})
    return out

# Itinerary history (Firestore)
def save_itinerary_history(uid: str, query: str, model: str, response: str):
    doc = {
        "query": query,
        "model": model,
        "response": response,
        "ts": datetime.now(timezone.utc)
    }
    db.collection("itineraries").document(uid).collection("runs").add(doc)
    
def load_itinerary_history(uid: str, limit: int = 5) -> List[Dict[str, Any]]:
    q = (
        db.collection("itineraries")
        .document(uid)
        .collection("runs")
        .order_by("ts", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [d.to_dict() for d in q.stream()]

# Auth UI
def login_form():
    st.subheader("Log in")
    if auth is None or db is None:
        st.info("Login feature temporarily disabled due to missing Firebase configuration.")
        return
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", key="email_login")
        password = st.text_input("Password", type="password", key="password_login")
        cols = st.columns([1, 1])
        login = cols[0].form_submit_button("Log in")
        goto_signup = cols[1].form_submit_button("Don't have an account? Sign up")

    if goto_signup:
        st.session_state["show_signup"] = True
        st.session_state["show_login"] = False
        st.rerun()

    if login:
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state.user = {
                "email": email,
                "uid": user["localId"],
                "idToken": user.get("idToken"),
            }
            # Nạp 5 lần tạo itinerary gần nhất vào session
            st.session_state.itin_history = load_itinerary_history(st.session_state.user["uid"], limit=5)
            msgs = load_last_messages(st.session_state.user["uid"], limit=16)
            st.session_state.messages = deque(
                msgs if msgs else [{"role": "assistant", "content": "Hello 👋 I am Mika. How can I help you today?"}],
                maxlen=16,
            )
            st.success("Login successful!")
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")


def signup_form():
    st.subheader("Sign up")
    if auth is None or db is None:
        st.info("Registration feature temporarily disabled due to missing Firebase configuration.")
        return
    with st.form("signup_form", clear_on_submit=False):
        email = st.text_input("Email", key="email_signup")
        password = st.text_input("Password (≥6 characters)", type="password", key="password_signup")
        cols = st.columns([1, 1])
        signup = cols[0].form_submit_button("Create account")
        goto_login = cols[1].form_submit_button("Already have an account? Log in")

    if goto_login:
        st.session_state["show_signup"] = False
        st.session_state["show_login"] = True
        st.rerun()

    if signup:
        try:
            _ = auth.create_user_with_email_and_password(email, password)
            st.success("Account created successfully! Please log in.")
            time.sleep(1.2)
            st.session_state["show_signup"] = False
            st.session_state["show_login"] = True
            st.rerun()
        except Exception as e:
            st.error(f"Sign-up failed: {e}")


# Chat UI
def chat_dialog():
    if not st.session_state.user:
        st.info("You need to log in to chat and save your history.")
        return

    try:
        body = st.container(border=True)
    except TypeError:
        body = st.container()

    # render lịch sử
    body.empty()
    with body:
        for m in list(st.session_state.messages):
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    user_input = st.chat_input("Enter message...")

    if not user_input:
        return

    # Push user -> UI + Firestore + session
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_message(st.session_state.user["uid"], "user", user_input)

    with body:
        with st.chat_message("user"):
            st.markdown(user_input)

        # Gọi model và hiển thị reply
        with st.chat_message("assistant"):
            with st.spinner("Mika is typing a response..."):
                try:
                    primer = {
                        "role": "system",
                        "content": "You are Mika, a concise, friendly travel/chat assistant. "
                                   "Answer clearly, in the user's language, and keep responses short.",
                    }
                    history = list(st.session_state.messages)
                    messages = [primer] + history
                    
                    model = st.session_state.get("chat_model", DEFAULT_MODEL)
                    cap = -1 if st.session_state.get("no_cap", True) else int(st.session_state.get("max_tokens", 512))

                    data = chat_backend(
                        messages=messages,
                        model=model,
                        want_json=False,          
                        num_predict=cap,
                        temperature=0.2,
                        timeout=DEFAULT_TIMEOUT,
                    )
                    reply = (extract_content(data) or "").strip() or "Sorry, I haven't received a response from the model yet."
                except requests.exceptions.ReadTimeout:
                    reply = "Server timeout. Please try again, or consider selecting a lighter model or reducing num_predict."
                except Exception as e:
                    reply = f"Call failed: {e}"

            st.markdown(reply)

    # Lưu assistant -> Firestore + session
    st.session_state.messages.append({"role": "assistant", "content": reply})
    save_message(st.session_state.user["uid"], "assistant", reply)
    st.rerun()


# Itinerary render helpers
def render_itinerary_text(text: str):
    st.subheader("Itinerary (raw)")
    st.write(text)


def render_itinerary_json(obj: Dict[str, Any]):
    st.subheader("Itinerary")
    days = obj.get("days") or []
    for i, day in enumerate(days, 1):
        label = day.get("date") or f"Day {i}"
        st.markdown(f"### 📅 {label}")
        for block in ["morning", "afternoon", "evening"]:
            items = day.get(block) or []
            if items:
                st.markdown(f"**{block.capitalize()}**")
                for it in items:
                    if isinstance(it, str):
                        st.markdown(f"- {it}")
                    else:
                        title = it.get("title") or it.get("name") or "(untitled)"
                        note = it.get("explain") or it.get("note") or ""
                        st.markdown(f"- **{title}** — {note}")

def fmt_ts(x) -> str:
    if isinstance(x, datetime):
        return x.astimezone().strftime("%Y-%m-%d %H:%M")
    try:
        s = str(x)
        # "2025-11-06T12:34:56Z" -> "2025-11-06T12:34:56+00:00"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(x)

# App state defaults
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = deque(
        [{"role": "assistant", "content": "Hello 👋 I am Mika. How can I help you today?"}],
        maxlen=16,
    )
if "show_signup" not in st.session_state:
    st.session_state.show_signup = False
if "show_login" not in st.session_state:
    st.session_state.show_login = True
if "chat_model" not in st.session_state:
    st.session_state.chat_model = DEFAULT_MODEL
    
# options + Local history
if "no_cap" not in st.session_state:
    st.session_state.no_cap = True           # mặc định: không giới hạn
if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 512        # mặc định hợp lệ cho slider
if "itin_history" not in st.session_state:
    st.session_state.itin_history = []       # lịch sử itinerary lưu cục bộ


# Top banner: endpoint status
st.caption(f"🔌 LLM_BACKEND = {BACKEND}")
if BACKEND == "ollama":
    ok, err = ping_ollama(BASE)
    # st.caption(f"🧪 OLLAMA_BASE = {BASE}")
    if not ok:
        st.error(f"Can't reach the model server. Make sure it is running and reachable.")


# Main UI
st.markdown("<h1 style='text-align:center;'>Streamlit Chat + Firebase Login</h1>", unsafe_allow_html=True)

if st.session_state.user:
    st.success(f"Logged in as {st.session_state.user['email']}")

    tab_itin, tab_chat = st.tabs(["Itinerary", "Chat"])

    # TAB ITINERARY
    with tab_itin:
        with st.form("plan_form"):
            c1, c2 = st.columns(2)
            with c1:
                origin = st.text_input("Origin city", "Ho Chi Minh City")
                start = st.date_input("Start date", date.today())
                interests = st.multiselect("Interests", ["food", "museums", "nature", "nightlife"], default=["food", "nature"])
            with c2:
                dest = st.text_input("Destination city", "Da Nang")
                end = st.date_input("End date", date.today() + timedelta(days=2))
                pace = st.selectbox("Pace", ["relaxed", "normal", "tight"], index=0)

            models = list_models_backend(DEFAULT_MODEL)
            model = st.selectbox("Model", models, index=(models.index(DEFAULT_MODEL) if DEFAULT_MODEL in models else 0))
            st.session_state.chat_model = model  # dùng luôn model này cho tab Chat
            want_json = st.checkbox("Return JSON", value=True)
            # no_cap = st.checkbox("Không giới hạn tokens", value=True)
            
            backend_ready = True
            if BACKEND == "ollama":
                ok, err = ping_ollama(BASE)
                if not ok:
                    backend_ready = False
                    st.error(f"Cannot connect to Ollama.: {err}")
            elif BACKEND == "openai" and not OPENAI_API_KEY:
                backend_ready = False
                st.error("BACKEND=openai but missing OPENAI_API_KEY in secrets/env.")
            elif BACKEND == "gemini" and not GEMINI_API_KEY:
                backend_ready = False
                st.error("BACKEND=gemini but missing GOOGLE_API_KEY (GEMINI_API_KEY) in secrets/env.")
            submitted = st.form_submit_button("Generate itinerary")

        with st.expander("⚙️ Advanced options", expanded=False):
            limitless = st.checkbox("Unlimited tokens", key="no_cap")
            safe_default = min(4096, max(64, int(st.session_state.get("max_tokens", 512))))
            st.slider(
                "Max tokens (num_predict)",
                64, 4096,
                value=safe_default, step=4,
                key="max_tokens",
                disabled=limitless   # <- luôn hiện slider, khóa khi Unlimited bật
            )
        if st.session_state.no_cap:
            st.caption("The model will run until it reaches EOS (num_predict = -1).")
        if submitted:
            if not backend_ready:
                st.info("Backend not ready (missing API key). Please configure it and try again.")
                st.stop()
                
            if end < start:
                st.error("End date must >= Start date.")
                st.stop()
                
            # Lấy cap từ state
            cap = -1 if st.session_state.no_cap else int(st.session_state.max_tokens)
            
            if want_json:
                sys_msg = (
                    "You are a concise travel planner. "
                    "Cover ALL dates from start to end (inclusive). "
                    "Each day has morning/afternoon/evening with ≥1 item each. "
                    "Each item includes a 10–20 word explanation. "
                    "Output ONLY valid JSON with shape: "
                    '{"days":[{"date":"YYYY-MM-DD",'
                    '"morning":[{"title":"...","explain":"..."}],'
                    '"afternoon":[{"title":"...","explain":"..."}],'
                    '"evening":[{"title":"...","explain":"..."}]}]}'
                )
            else:
                sys_msg = (
                    "You are a concise travel planner. "
                    "Write a readable day-by-day itinerary covering ALL dates (start..end), "
                    "with morning/afternoon/evening blocks; each item has a 10–20 word explanation."
                )


            user_msg = (
                f"Origin: {origin}; Destination: {dest}; "
                f"Dates: {start.isoformat()} to {end.isoformat()}; "
                f"Interests: {', '.join(interests) if interests else 'none'}; "
                f"Pace: {pace}."
            )

            try:
                data = chat_backend(
                    messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                    model=model,
                    want_json=want_json,
                    num_predict=cap,
                    temperature=0.2,
                    timeout=DEFAULT_TIMEOUT,
                )
                content = extract_content(data)

                if want_json:
                    try:
                        obj = json.loads(content)  
                        render_itinerary_json(obj)
                    except Exception:
                        st.warning("The model did not return valid JSON. Displaying raw text instead.")
                        render_itinerary_text(content)
                else:
                    render_itinerary_text(content)
                    
                # Render history itinerary vào Firestore (persist)
                save_itinerary_history(st.session_state.user["uid"], user_msg, model, content) 
                
                # Render history itinerary (LOCAL SESSION (first list -> max 5))
                st.session_state.itin_history.insert(0, {
                    "query": user_msg,
                    "model": model,
                    "response": content,
                    "ts": datetime.now(timezone.utc).isoformat()
                })
                st.session_state.itin_history = st.session_state.itin_history[:5]

            except requests.exceptions.ReadTimeout:
                st.error("Server timeout. Try selecting a lighter model (e.g., llama3.2:3b) or reducing num_predict.")
            except Exception as e:
                st.error(f"Model invocation error: {e}")
                
        with st.expander("🕘 Itinerary history (local)", expanded=False):
            if not st.session_state.itin_history:
                st.caption("No history available yet.")
            else:
                for i, h in enumerate(st.session_state.itin_history, 1):
                    # Hiển thị lịch sử theo giờ địa phương
                    ts_fmt = fmt_ts(h.get("ts", ""))
                    st.markdown(f"**#{i}** — {ts_fmt} — *{h.get('model','')}*")
                    st.code(h.get("query",""), language="text")
                    # Tự phát hiện JSON thay vì phụ thuộc vào checkbox hiện tại
                    resp_text = h.get("response","") or ""
                    try:
                        st.json(json.loads(resp_text))
                    except Exception:
                        st.text(resp_text)
                    st.markdown("---")

    # TAB CHAT
    with tab_chat:
        chat_dialog()

    # Đăng xuất
    _, c, _ = st.columns([1, 1, 1])
    if c.button("Log out", type="primary"):
        st.session_state.user = None
        st.session_state.chat_model = DEFAULT_MODEL
        st.session_state.messages = deque(
            [{"role": "assistant", "content": "Hello 👋 I am Mika. How can I help you today?"}],
            maxlen=16,
        )
        st.rerun()

else:
    # Chưa đăng nhập
    if st.session_state.show_signup:
        signup_form()
    elif st.session_state.show_login:
        login_form()
