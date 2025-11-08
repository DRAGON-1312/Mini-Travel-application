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
* UI Theme (THEME_BG)

Edit `app.py` to:

1) **Endpoint & defaults**
* BASE (Ollama endpoint selector block): Line 24-30.
* DEFAULT_MODEL: Line 32.
* DEFAULT_TIMEOUT: Line 33.
* DEFAULT_NUM_PREDICT: Line 34.

2) **UI & layout**
*Page config (title, icon, layout): Line 17-21.
* Want to hide or customize the message when Ollama is not reachable: Line 550-555.
* Main heading: Line 559-560 (inject_travel_theme() - Line 49-84 & hero_header() - Line 87-107).
* Tab names: Line 565.
* Form fields (Itinerary tab): Line 571-578.
* Model selector (shared for Chat): Line 581-582.
* "Return JSON" checkbox: Line 583.
* Schedule creation button: Line 598
* Token control (Unlimited & slider): Line 600-609. 
    (Note: EOS below (Line 611)).
* Itinerary renderer (text): Line 489-491.
* Itinerary renderer (JSON): Line 494-511.
* Display itinerary history (local panel): Line 689-704.
* Render chat history: Line 432-436.

3) **Chat persona, greeting, temperature**
* Primer for Chat: Line 455-459.
* Default Greeting: Line 381 (Load history after login), Line 530 (Initialize session for the first time), Line 716 (after logout)
* Temperature, num_predict for Chat: Line 471-472.

4) **Backends & AI integration**
* Select backend + configure key: Line 37-46.
* Ping Ollama / model list from /api/tags: Line 114-134.
* Ollama wrapper: Line 137-188.
* OpenAI wrapper: Line 196-224.
* Gemini wrapper: Line 227-254.
* Dispatcher: Line 257-274.
* Model list by backend (populate into dropdown): Line 278-285.

5) **Authorization & data storage**
* Require login to use Chat: Line 421-423.
* Form sign in: Line 352-387.
* Form sign up: Line 390-416.
* Firebase init (Auth + Firestore): Line 289-306.
* Save chat history (Firestore): Line 310-312.
* Read chat history (Firestore): Line 315-329.
* Save itinerary history (Firestore): Line 332-339.
* Read itinerary history (Firestore): Line 341-349.
* Save itinerary history to session (retain up to 5 entries): Line 676-682.

6) **Itinerary generation prompt & validation**
* Validate date: Line 617-619 
* Prompt JSON (Itinerary): Line 625-635
* Text-based prompt: Line 636-641
* User message: Line 644-649

7) **Historical time format (Line 513-523)**
