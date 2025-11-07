# Mini-travel Application (Streamlit + Firebase + Ollama)

* A simple mini-travel web app that lets users **log in, log out, chat, and generate a day-by-day itinerary** 
(morning/afternoon/evening, short explanations) using an LLM.
* Backends supported: **Ollama (default), OpenAI, and Gemini**. The UI is built with **Streamlit** and 
authentication/history are stored in **Firebase** (Auth + Firestore).

## 🚀 Features

* **Two tabs**: Itinerary & Chat (Streamlit UI).
* **Form inputs**: origin, destination, dates, interests, pace.
* **Multi-backend LLM**: Ollama (default), OpenAI, Gemini; one model selector shared by both tabs.
* **Structured itinerary**: morning / afternoon / evening with short explanations; optional strict JSON (fallback to raw text).
* **Auth & history**: Firebase Email/Password + Firestore for chat & itinerary history.
* **Token control**: unlimited or max-tokens slider.

## 🧰 Requirements

* Python 3.10+ (recommended: 3.11)
* Pip + venv
* Streamlit
* Other dependencies in `requirements.txt`

## ⚙️ Installation

```bash
git clone https://github.com/DRAGON-1312/Mini-Travel-application.git
cd "Mini-Travel-application/mini-travel app/SourceCode"
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

## 🔐 Create `.streamlit/secrets.toml` from `temp.txt`

### macOS / Linux
```bash

mkdir -p .streamlit
cp temp.txt .streamlit/secrets.toml

# If you run from repo root
mkdir -p ./.streamlit
cp SourceCode/temp.txt ./.streamlit/secrets.toml

# then edit your keys
nano .streamlit/secrets.toml   
```

### Windows (PowerShell)
```bash
# If you run from SourceCode
mkdir .streamlit -Force
Copy-Item temp.txt .streamlit\secrets.toml
notepad .streamlit\secrets.toml

# If you run from repo root
mkdir .streamlit -Force
Copy-Item SourceCode\temp.txt .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

## 🌐 Run on Colab/Kaggle (ngrok tunnel)

> You must add a **Colab Secret** named `NGROK_AUTHTOKEN` to obtain a public URL for your local Ollama.

**Step 1 — Add the secret in Colab**
1) Click the **🔑 Secrets** panel in Colab.
2) Create a new key: **`NGROK_AUTHTOKEN`** (copy from dashboard.ngrok.com)

**Step 2 — Start ngrok & get the public URL**

**Step 3 — Point the app to this URL**
* Edit ./.streamlit/secrets.toml:
OLLAMA_BASE = "<paste the NGROK URL here>"

## ▶️ Run

```bash
streamlit run app.py
```

## 🛠️ Customization

Edit `secrets.toml` to:
* Select backend (enable one of the three - ollama, openai, gemini)
* firebase (firebase_client & firebase_admin)

Edit `app.py` to:

1) **Endpoint & defaults**
* BASE: Line 24-30.
* DEFAULT_MODEL: Line 32.
* DEFAULT_TIMEOUT: Line 33.
* DEFAULT_NUM_PREDICT: Line 34.

2) **UI & layout**
*Page config (title, icon, layout): Line 17-21.
* Want to hide or customize the message when Ollama is not reachable: Line 486-491.
* Main heading: Line 495.
* Tab names: Line 500.
* Form fields (Itinerary tab): Line 506-513.
* Model selector (shared for Chat): Line 516-517.
* "Return JSON" checkbox: Line 518.
* Token control (Unlimited & slider): Line 536-544. 
    (Note: EOS below (L546)).
* Itinerary renderer (text): Line 426-428.
* Itinerary renderer (JSON): Line 431-447.
* Display itinerary history (local panel): Line 624-639.
* Render chat history: Line 372-373.

3) **Chat persona, greeting, temperature**
* Primer for Chat: Line 392-395.
* Default Greeting: Line 319 (Load history after login), Line 465-467 (Initialize session for the first time), Line 650-652 (after logout)
* Temperature, num_predict for Chat: Line 408, 409.

4) **Backends & AI integration**
* Select backend + configure key: Line 37-46.
* Ping Ollama / model list from /api/tags: Line 52-72.
* Ollama wrapper: Line 75-126.
* OpenAI wrapper: Line 134-162.
* Gemini wrapper: Line 165-192.
* Dispatcher: Line 195-212.
* Model list by backend (populate into dropdown): Line 216-223.

5) **Authorization & data storage**
* Require login to use Chat: Line 359-361.
* Form sign in: Line 290-325.
* Form sign up: Line 328-354.
* Firebase init (Auth + Firestore): Line 227-244.
* Save chat history (Firestore): Line 248-250.
* Read chat history (Firestore): Line 253-267.
* Save itinerary history (Firestore): Line 270-277.
* Read itinerary history (Firestore): Line 279-287.
* Save itinerary history to session (retain up to 5 entries): Line 611-617.

6) **Itinerary generation prompt & validation**
* Prompt JSON (Itinerary): Line 560-570
* Text-based prompt: Line 571-576
* User message: Line 579-584
* Validate date: Line 552-554 

7) **Historical time format (Line 449-459)**
