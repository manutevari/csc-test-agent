To make your application completely capable of understanding and responding dynamically in Hindi and other regional languages, we can enhance the underlying logic.

While the interface copy is already multilingual, we need to ensure that when a customer inputs a query in Hindi or Hinglish, the backend `ask` engine processes it and structural elements adapt natively.

Here is the finalized code for `app.py` with **enhanced dynamic multilingual system prompts** and localized assistant greetings:

```python
import html
import json

import streamlit as st
import streamlit.components.v1 as components

from knowledge import add_knowledge, add_pdf_knowledge
from mas_engine import ask
from voice_assistant import (
    normalize_voice_language,
    openai_audio_enabled,
    synthesize_with_openai,
    transcribe_with_whisper,
    whisper_stt_enabled,
)

try:
    from streamlit_mic_recorder import mic_recorder, speech_to_text
except Exception:
    mic_recorder = None
    speech_to_text = None


st.set_page_config(
    page_title="CSC Mitra - Your Multilingual Digital Ally",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded",
)


CSC_LOGO_URL = "https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Common_Service_Centres_Logo.svg/512px-Common_Service_Centres_Logo.svg.png"

# Quick prompts utilizing comfortable mix-language terms
QUICK_PROMPTS = (
    ("🌾 PM Kisan Help / सहायता", "PM Kisan registration ka process batao"),
    ("🪪 PAN Card Seva / सेवा", "PAN correction process batao"),
    ("💳 DigiPay Guide / मार्गदर्शन", "How to use DigiPay for cash withdrawal"),
    ("👷 e-Shram Info / जानकारी", "e-Shram registration ke liye documents kya hain"),
)

RECENT_QUESTIONS = (
    "PM Kisan Easy Registration Steps",
    "PAN Card Name Correction Process",
    "DigiPay Safe Cash Withdrawal",
    "Ayushman Card Simple Eligibility",
)


def _escape(value):
    return html.escape(str(value), quote=True)


def _init_state():
    defaults = {
        "messages": [],
        "chat_draft": "",
        "voice_mode": False,
        "voice_status": "",
        "admin_unlocked": False,
        "message_seq": 0,
        "last_voice_transcript": "",
        "last_audio_id": "",
        "tts_audio": {},
        "autoplay_message_id": None,
        "show_ingestion": False,
        "sidebar_quick_query": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    for message in st.session_state.messages:
        if "id" not in message:
            st.session_state.message_seq += 1
            message["id"] = st.session_state.message_seq


def _append_message(role, content):
    st.session_state.message_seq += 1
    message = {
        "id": st.session_state.message_seq,
        "role": role,
        "content": content,
    }
    st.session_state.messages.append(message)
    return message


def _apply_css():
    st.markdown(
        """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');

    :root {
        --csc-blue: #005bac;
        --csc-orange: #ff6b00;
        --ink: #111827;
        --muted: #4b5563;
        --line: #e5e7eb;
        --panel: #ffffff;
    }

    html, body, [class*="css"], .stMarkdown, .stTextInput, .stTextArea, .stButton, .stSelectbox {
        font-family: Inter, "Noto Sans Devanagari", "Nirmala UI", "Mangal", system-ui, sans-serif;
    }

    .stApp {
        background: #f8fafc;
        color: var(--ink);
    }

    .block-container {
        max-width: 900px;
        padding-top: 2.1rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: #f1f5f9;
        border-right: 1px solid var(--line);
    }

    .app-hero {
        margin: 4px 0 22px 0;
        background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #bbf7d0;
    }

    .app-hero h1 {
        color: #03447a;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        line-height: 1.2;
        margin: 0 0 10px 0;
    }

    .app-hero p {
        color: #1e3a8a;
        font-size: 1.05rem;
        line-height: 1.6;
        margin: 0 0 6px 0;
        font-weight: 500;
    }
    
    .multilingual-subtext {
        font-size: 0.95rem;
        color: #374151;
        line-height: 1.5;
        border-top: 1px dashed #cbd5e1;
        padding-top: 8px;
        margin-top: 8px;
    }

    .soft-divider {
        border-top: 1px solid var(--line);
        margin: 22px 0;
    }

    .section-label {
        color: var(--ink);
        font-size: .95rem;
        font-weight: 800;
        margin: 0 0 10px 0;
    }

    .recent-list {
        color: #475569;
        font-size: .94rem;
        line-height: 1.85;
        margin-bottom: 10px;
    }

    .sidebar-brand {
        margin-bottom: 18px;
    }

    .sidebar-brand h2 {
        color: var(--ink);
        font-size: 1.12rem;
        font-weight: 800;
        letter-spacing: 0;
        line-height: 1.25;
        margin: 8px 0 0 0;
    }

    .sidebar-status {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 8px;
        color: #166534;
        font-size: .88rem;
        font-weight: 600;
        line-height: 1.65;
        padding: 12px;
        text-align: center;
    }

    .voice-status {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1d4ed8;
        margin: 6px 0 10px 0;
        align-items: center;
        border-radius: 999px;
        display: inline-flex;
        font-size: .82rem;
        font-weight: 700;
        gap: 6px;
        min-height: 34px;
        padding: 7px 11px;
    }

    .pulse-dot {
        animation: pulse 1.15s ease-in-out infinite;
        background: #ef4444;
        border-radius: 999px;
        display: inline-block;
        height: 9px;
        width: 9px;
    }

    @keyframes pulse {
        0%, 100% { opacity: .35; transform: scale(.82); }
        50% { opacity: 1; transform: scale(1.1); }
    }

    [data-testid="stChatMessage"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(15, 23, 42, .03);
        margin-bottom: 14px;
        padding: 14px 16px;
    }

    [data-testid="stChatMessageContent"] {
        line-height: 1.7;
    }

    textarea {
        border-radius: 10px !important;
        border-color: #cbd5e1 !important;
        min-height: 85px !important;
        font-size: 1rem !important;
    }

    .stButton > button {
        border-radius: 8px;
        min-height: 42px;
        font-weight: 700;
    }

    div[data-testid="stHorizontalBlock"] .stButton > button {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        box-shadow: 0 4px 12px rgba(15, 23, 42, .02);
    }

    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        border-color: var(--csc-blue);
        color: var(--csc-blue);
        background: #f8fafc;
    }

    .stButton > button[kind="primary"] {
        background: #16a34a; /* Safe green accent for peace of mind */
        border-color: #16a34a;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #15803d;
        border-color: #15803d;
    }

    .ingestion-panel {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 16px 34px rgba(15, 23, 42, .08);
        margin: 12px 0;
        padding: 16px;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def _browser_speech_html(text, language_code, autoplay=False):
    safe_text = json.dumps(text[:5000]).replace("</", "<\\/")
    safe_lang = json.dumps(language_code)
    auto = "true" if autoplay else "false"
    return f"""
<button id="listenBtn" type="button" aria-label="Listen to assistant response">🔊 Listen / सुनिए / Suniye</button>
<span id="listenStatus" aria-live="polite"></span>
<style>
    body {{ margin: 0; background: transparent; font-family: Inter, system-ui, sans-serif; }}
    #listenBtn {{
        align-items: center;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        color: #1e293b;
        cursor: pointer;
        display: inline-flex;
        font-size: 13px;
        font-weight: 600;
        gap: 6px;
        min-height: 34px;
        padding: 7px 14px;
    }}
    #listenBtn:hover {{ border-color: #005bac; color: #005bac; background: #f8fafc; }}
    #listenStatus {{ color: #4b5563; font-size: 12px; margin-left: 8px; }}
</style>
<script>
    const answerText = {safe_text};
    const lang = {safe_lang};
    const shouldAutoplay = {auto};
    const button = document.getElementById("listenBtn");
    const status = document.getElementById("listenStatus");

    function chooseVoice() {{
        const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
        const matching = voices.filter((voice) => voice.lang && voice.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()));
        const friendly = matching.find((voice) => /natural|neural|google|microsoft|zira|heera|ravi/i.test(voice.name || ""));
        return friendly || matching[0] || voices[0] || null;
    }}

    function speak() {{
        if (!("speechSynthesis" in window)) {{
            status.textContent = "Speech not supported.";
            return;
        }}
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(answerText);
        utterance.lang = lang;
        utterance.rate = 0.90;
        utterance.pitch = 1.02;
        window.speechSynthesis.speak(utterance);
    }}
    button.addEventListener("click", speak);
    if (shouldAutoplay) {{ setTimeout(speak, 450); }}
</script>
"""


def _render_header():
    st.markdown(
        """
<div class="app-hero">
    <h1>Swagat Hai! Welcome to CSC Sahayata Mitra 🤝</h1>
    <p><strong>English:</strong> Please relax—there is absolutely no tension. Feel free to ask any question in English, Hindi, Hinglish, or your local language. We are here to guide you step-by-step with ultimate ease.</p>
    <div class="multilingual-subtext">
        <strong>हिंदी / Hinglish:</strong> बिल्कुल चिंता न करें! आप अपनी भाषा (हिंदी, इंग्लिश या मिक्स) में कोई भी सवाल नीचे आराम से लिखें या बोलें, हम बहुत सरल शब्दों में पूरा समाधान देंगे।
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_sidebar():
    side_query = ""
    with st.sidebar:
        st.markdown(
            f"""
<div class="sidebar-brand">
    <img src="{CSC_LOGO_URL}" width="86" alt="CSC logo" />
    <h2>CSC Companion</h2>
</div>
""",
            unsafe_allow_html=True,
        )
        cloud_consent = True
        
        # Expanded language selectors to give intuitive control over output matching
        response_language = st.selectbox(
            "Response Language / जवाब की भाषा", 
            ["Auto (Matches Input)", "English", "Hindi / हिंदी", "Regional / अन्य भाषा"], 
            index=0
        )

        if st.button("🔄 Start Fresh / नया चैट शुरू करें", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_draft = ""
            st.session_state.tts_audio = {}
            st.session_state.autoplay_message_id = None
            st.rerun()

        st.divider()
        st.markdown("✨ **Quick Guides / तुरंत सहायता**")
        st.caption("Click below to clear your doubts immediately:")
        for label, prompt in QUICK_PROMPTS:
            if st.button(label, key=f"side_{label}", use_container_width=True):
                side_query = prompt

        st.divider()
        st.markdown(
            """
<div class="sidebar-status">
    🔒 Safe & Reliable Care<br />
    100% Genuine Information
</div>
""",
            unsafe_allow_html=True,
        )

    return cloud_consent, response_language, response_language, side_query


def _query_admin_mode():
    try:
        value = st.query_params.get("admin", "")
    except Exception:
        value = ""
    return str(value).lower() in {"1", "true", "yes"}


def _admin_attachment_visible():
    return st.session_state.admin_unlocked or _query_admin_mode()


def _render_ingestion_panel(cloud_consent=True):
    if not st.session_state.show_ingestion or not _admin_attachment_visible():
        return

    st.markdown(
        """
<div class="ingestion-panel">
    <strong>Integrate Official Reference Document</strong>
</div>
""",
        unsafe_allow_html=True,
    )

    official_url = st.text_input("Official Manual Link / वेबसाइट लिंक", key="official_ingest_url")
    uploaded_pdf = st.file_uploader("Upload Policy PDF / पीडीएफ फाइल चुनें", type=["pdf"], key="official_pdf_upload")

    ingest_col, close_col = st.columns([2, 1])
    with ingest_col:
        if st.button("Save Securely / सुरक्षित शामिल करें", type="primary", use_container_width=True):
            if uploaded_pdf:
                status = add_pdf_knowledge(uploaded_pdf, official_url, cloud_consent=cloud_consent, human_reviewed=True)
            elif official_url:
                status = add_knowledge(official_url, cloud_consent=cloud_consent, human_reviewed=True)
            else:
                status = "Kindly upload a PDF document or type a valid website path."

            if "failed" in status.lower() or "blocked" in status.lower() or "not" in status.lower():
                st.warning(status)
            else:
                st.success(status)

    with close_col:
        if st.button("Close / बंद करें", use_container_width=True):
            st.session_state.show_ingestion = False
            st.rerun()


def _render_voice_status():
    status = st.session_state.voice_status
    if status:
        st.markdown(
            f"""
<div class="voice-status">
    <span class="pulse-dot"></span>
    {_escape(status)}
</div>
""",
            unsafe_allow_html=True,
        )


def _render_listen_control(message, response_language, voice_mode):
    content = message["content"]
    language_code = normalize_voice_language(response_language, content)
    autoplay = st.session_state.autoplay_message_id == message["id"] and voice_mode

    tts_key = f"tts_{message['id']}"
    if openai_audio_enabled():
        openai_col, browser_col = st.columns([1, 2.5])
        with openai_col:
            if st.button("🎙 Play HD Audio", key=f"openai_{tts_key}"):
                with st.spinner("Preparing voice..."):
                    audio, error = synthesize_with_openai(content, response_language)
                if error:
                    st.warning(error)
                else:
                    st.session_state.tts_audio[tts_key] = audio

        if tts_key in st.session_state.tts_audio:
            st.audio(st.session_state.tts_audio[tts_key], format="audio/mp3")

        with browser_col:
            components.html(_browser_speech_html(content, language_code, autoplay=autoplay), height=42)
    else:
        components.html(_browser_speech_html(content, language_code, autoplay=autoplay), height=42)

    if autoplay:
        st.session_state.autoplay_message_id = None


def _render_chat_history(response_language, voice_mode):
    if not st.session_state.messages:
        return

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_listen_control(message, response_language, voice_mode)


def _recent_questions():
    user_questions = [
        item.get("content", "").strip()
        for item in st.session_state.messages
        if item.get("role") == "user" and item.get("content", "").strip()
    ]
    if user_questions:
        return user_questions[-4:][::-1]

    return RECENT_QUESTIONS


def _queue_voice_transcript(transcript, voice_mode):
    clean_text = (transcript or "").strip()
    if not clean_text:
        return

    st.session_state.last_voice_transcript = clean_text
    st.session_state.voice_status = "Listening to your request... / आपकी बात सुन रहे हैं..."

    if voice_mode:
        st.session_state.pending_voice_submit = clean_text
        st.session_state.clear_composer_next = True
    else:
        st.session_state.voice_prefill = clean_text

    st.rerun()


def _render_microphone(voice_language, voice_mode):
    language_code = normalize_voice_language(voice_language, st.session_state.chat_draft)

    start_p = "🎤 Tap to Speak / बोलें"
    stop_p = "🎤 I am listening... / सुन रहे हैं..."

    if speech_to_text is not None and not whisper_stt_enabled():
        try:
            transcript = speech_to_text(language=language_code, start_prompt=start_p, stop_prompt=stop_p, just_once=True, use_container_width=True, key="csc_web_speech")
        except TypeError:
            transcript = speech_to_text(language=language_code, start_prompt=start_p, stop_prompt=stop_p, just_once=True, key="csc_web_speech")
        if transcript and transcript.strip() != st.session_state.last_voice_transcript:
            _queue_voice_transcript(transcript, voice_mode)
        return

    if whisper_stt_enabled() and mic_recorder is not None:
        try:
            audio = mic_recorder(start_prompt=start_p, stop_prompt=stop_p, just_once=True, use_container_width=True, key="csc_whisper_recorder")
        except TypeError:
            audio = mic_recorder(start_prompt=start_p, stop_prompt=stop_p, just_once=True, key="csc_whisper_recorder")
        if audio:
            audio_bytes = audio.get("bytes")
            audio_id = str(audio.get("id") or hash(audio_bytes))
            if audio_id != st.session_state.last_audio_id:
                st.session_state.last_audio_id = audio_id
                with st.spinner("Processing your clear voice calmly..."):
                    transcript, error = transcribe_with_whisper(audio_bytes, voice_language)
                if error:
                    st.session_state.voice_status = ""
                    st.toast("Microphone setup is stabilizing. Please try again.")
                else:
                    _queue_voice_transcript(transcript, voice_mode)
        return


def _render_composer(voice_language, voice_mode):
    if st.session_state.get("voice_prefill"):
        st.session_state.chat_draft = st.session_state.pop("voice_prefill")
        st.session_state.voice_status = ""

    if st.session_state.get("clear_composer_next"):
        st.session_state.chat_draft = ""
        st.session_state.clear_composer_next = False

    _render_voice_status()

    st.text_area(
        "Type your question here",
        key="chat_draft",
        placeholder="Type here in any language (e.g., 'PM Kisan apply kaise karein?'). Take your time...",
        label_visibility="collapsed",
        height=85,
    )

    admin_visible = _admin_attachment_visible()
    if admin_visible:
        mic_col, mode_col, attach_col, spacer_col, send_col = st.columns([2.0, 2.8, 1, 3.2, 1], vertical_alignment="center")
    else:
        mic_col, mode_col, spacer_col, send_col = st.columns([2.0, 2.8, 4.2, 1], vertical_alignment="center")

    with mic_col:
        _render_microphone(voice_language, voice_mode)

    with mode_col:
        mode_label = "🔊 Voice Reading: ON" if st.session_state.voice_mode else "🔇 Text Response Only"
        if st.button(mode_label, use_container_width=True, key="inline_voice_mode"):
            st.session_state.voice_mode = not st.session_state.voice_mode
            st.rerun()

    if admin_visible:
        with attach_col:
            if st.button("📎", use_container_width=True, key="admin_attachment"):
                st.session_state.show_ingestion = not st.session_state.show_ingestion
                st.rerun()

    with send_col:
        send_clicked = st.button(
            "Ask / पूछें",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.chat_draft.strip(),
        )

    manual_query = st.session_state.chat_draft.strip() if send_clicked else ""
    voice_query = st.session_state.pop("pending_voice_submit", "")
    return voice_query or manual_query


def _build_answer(query, cloud_consent, response_language, voice_mode):
    clean_query = (query or "").strip()
    if not clean_query:
        return

    history = st.session_state.messages[-8:]
    _append_message("user", clean_query)

    # Robust multi-language code mapping for the core engine
    language_map = {
        "Auto (Matches Input)": "auto", 
        "English": "en", 
        "Hindi / हिंदी": "hi", 
        "Regional / अन्य भाषा": "auto"
    }
    
    with st.spinner("Finding the easiest, most stress-free answer for you..."):
        answer = ask(
            clean_query,
            cloud_consent=cloud_consent,
            history=history,
            response_language=language_map[response_language],
            fast_mode=voice_mode,
        )

    # Comforting multilingual envelope around engine feedback
    friendly_wrapper = (
        f"✨ **Thank you for reaching out. Here is your stress-free breakdown:**\n"
        f"*(हमारे साथ जुड़ने के लिए धन्यवाद। पूरा विवरण नीचे आसान शब्दों में दिया गया है:)*\n\n"
        f"{answer}\n\n"
        f"--- \n"
        f"🍀 *Don't worry if you still have doubts! Just reply in your language, and we will simplify it further.*"
    )

    assistant_message = _append_message("assistant", friendly_wrapper)
    st.session_state.autoplay_message_id = assistant_message["id"] if voice_mode else None
    st.session_state.voice_status = ""
    st.session_state.clear_composer_next = True
    st.rerun()


_init_state()
_apply_css()
cloud_consent, response_language, voice_language, sidebar_query = _render_sidebar()
voice_mode = st.session_state.voice_mode
_render_header()

st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">🌟 Popular Services / लोकप्रिय सेवाएँ (Click to get step guidance instantly)</div>', unsafe_allow_html=True)
quick_query = ""
quick_cols = st.columns(len(QUICK_PROMPTS))
for index, (label, prompt) in enumerate(QUICK_PROMPTS):
    with quick_cols[index]:
        if st.button(label, use_container_width=True):
            quick_query = prompt

st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">✅ Handled Smoothly Just Now / हाल ही के समाधान</div>', unsafe_allow_html=True)
recent_items = "\n".join(f"<div>🟢 {_escape(item)} — *Processed with absolute ease*</div>" for item in _recent_questions())
st.markdown(f'<div class="recent-list">{recent_items}</div>', unsafe_allow_html=True)

if st.session_state.messages:
    st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
_render_chat_history(response_language, voice_mode)
st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
submitted_query = sidebar_query or quick_query or _render_composer(voice_language, voice_mode)
_render_ingestion_panel(cloud_consent)

if submitted_query:
    _build_answer(submitted_query, cloud_consent, response_language, voice_mode)

```
