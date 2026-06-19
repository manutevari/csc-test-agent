import html
import json

import streamlit as st
import streamlit.components.v1 as components

from knowledge import add_knowledge, add_pdf_knowledge
from hitl import list_pending_reviews, resolve_review
from mas_engine import ask
from voice_assistant import (
    normalize_voice_language,
    transcribe_with_whisper,
    whisper_stt_enabled,
)

try:
    from streamlit_mic_recorder import mic_recorder, speech_to_text
except Exception:
    mic_recorder = None
    speech_to_text = None


st.set_page_config(
    page_title="CSC Mitra - CSC AI Assistant",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded",
)


CSC_LOGO_URL = "https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Common_Service_Centres_Logo.svg/512px-Common_Service_Centres_Logo.svg.png"

QUICK_PROMPTS = (
    ("🌾 PM Kisan Sahayata", "PM Kisan registration ka process batao"),
    ("🪪 PAN Card Seva", "PAN correction process batao"),
    ("💳 DigiPay Guide", "How to use DigiPay for cash withdrawal"),
    ("👷 e-Shram Registration", "e-Shram registration ke liye documents kya hain"),
)

RECENT_QUESTIONS = (
    "PM Kisan registration process",
    "PAN correction steps",
    "DigiPay settlement help",
    "Ayushman card eligibility",
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
        --soft-green: #f0fdf4;
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
        background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
        border: 1px solid #bbf7d0;
        border-radius: 8px;
        margin: 4px 0 22px 0;
        padding: 20px 22px;
    }

    .app-hero h1 {
        color: #03447a;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0;
        line-height: 1.16;
        margin: 0 0 6px 0;
    }

    .app-hero p {
        color: #1e3a8a;
        font-size: .98rem;
        font-weight: 500;
        line-height: 1.58;
        margin: 0;
    }

    .soft-divider {
        border-top: 1px solid var(--line);
        margin: 22px 0;
    }

    .section-label {
        color: var(--ink);
        font-size: .9rem;
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
        font-size: 1.08rem;
        font-weight: 800;
        letter-spacing: 0;
        line-height: 1.25;
        margin: 8px 0 0 0;
    }

    .sidebar-brand p {
        color: var(--muted);
        font-size: .84rem;
        line-height: 1.35;
        margin: 3px 0 0 0;
    }

    .sidebar-status {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 8px;
        color: #166534;
        font-size: .86rem;
        font-weight: 750;
        line-height: 1.65;
        padding: 12px;
        text-align: center;
    }

    .hero-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-end;
    }

    .hero-badge, .voice-status {
        align-items: center;
        border-radius: 999px;
        display: inline-flex;
        font-size: .82rem;
        font-weight: 700;
        gap: 6px;
        min-height: 34px;
        padding: 7px 11px;
        white-space: nowrap;
    }

    .hero-badge {
        background: #ffffff;
        border: 1px solid var(--line);
        color: #334155;
    }

    .voice-status {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1d4ed8;
        margin: 6px 0 10px 0;
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

    .prompt-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 6px 0 14px 0;
    }

    [data-testid="stChatMessage"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 10px 26px rgba(15, 23, 42, .045);
        margin-bottom: 12px;
        padding: 10px 12px;
    }

    [data-testid="stChatMessageContent"] {
        line-height: 1.64;
    }

    textarea {
        border-radius: 8px !important;
        border-color: #cbd5e1 !important;
        font-size: 1rem !important;
        min-height: 80px !important;
    }

    .stButton > button {
        border-radius: 8px;
        min-height: 42px;
        font-weight: 750;
    }

    div[data-testid="stHorizontalBlock"] .stButton > button {
        background: #ffffff;
        border: 1px solid #d8dee8;
        box-shadow: 0 8px 18px rgba(15, 23, 42, .035);
    }

    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        border-color: var(--csc-blue);
        color: var(--csc-blue);
        background: #f8fafc;
    }

    .stButton > button[kind="primary"] {
        background: #16a34a;
        border-color: #16a34a;
    }

    .stButton > button[kind="primary"]:hover {
        background: #15803d;
        border-color: #15803d;
    }

    .empty-state {
        background: transparent;
        border: 0;
        border-radius: 8px;
        color: var(--muted);
        padding: 4px 0 12px 0;
        text-align: left;
    }

    .ingestion-panel {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 16px 34px rgba(15, 23, 42, .08);
        margin: 12px 0;
        padding: 16px;
    }

    .small-note {
        color: var(--muted);
        font-size: .86rem;
        line-height: 1.45;
        margin-top: 8px;
    }

    @media (max-width: 760px) {
        .block-container {
            padding-left: .85rem;
            padding-right: .85rem;
        }

        .app-hero {
            align-items: flex-start;
            flex-direction: column;
            padding: 16px;
        }

        .hero-badges {
            justify-content: flex-start;
        }

        .app-hero h1 {
            font-size: 1.45rem;
        }
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
<button id="listenBtn" type="button" aria-label="Listen to assistant response">🔊 Listen to Response</button>
<button id="stopBtn" type="button" aria-label="Stop reading assistant response">⏹ Stop</button>
<span id="listenStatus" aria-live="polite"></span>
<style>
    body {{
        margin: 0;
        background: transparent;
        font-family: Inter, system-ui, sans-serif;
    }}
    #listenBtn, #stopBtn {{
        align-items: center;
        background: #ffffff;
        border: 1px solid #d6dde8;
        border-radius: 8px;
        color: #1e293b;
        cursor: pointer;
        display: inline-flex;
        font-size: 13px;
        font-weight: 700;
        gap: 6px;
        min-height: 34px;
        padding: 7px 11px;
    }}
    #stopBtn {{
        margin-left: 6px;
    }}
    #listenBtn:hover, #stopBtn:hover {{
        border-color: #005bac;
        color: #005bac;
    }}
    #listenStatus {{
        color: #4b5563;
        font-size: 12px;
        margin-left: 8px;
    }}
</style>
<script>
    const answerText = {safe_text};
    const lang = {safe_lang};
    const shouldAutoplay = {auto};
    const button = document.getElementById("listenBtn");
    const stopButton = document.getElementById("stopBtn");
    const status = document.getElementById("listenStatus");
    let queue = [];
    let activeIndex = 0;

    function chooseVoice() {{
        const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
        const matching = voices.filter((voice) => voice.lang && voice.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()));
        const friendly = matching.find((voice) => /natural|neural|google|microsoft|zira|heera|ravi/i.test(voice.name || ""));
        return friendly || matching[0] || voices[0] || null;
    }}

    function speechChunks(text) {{
        const cleaned = text
            .replace(/https?:\\/\\/\\S+/g, "official link available in the answer")
            .replace(/[*#`_>-]/g, "")
            .replace(/\\s+/g, " ")
            .trim();
        const sentences = cleaned.match(/[^.!?।]+[.!?।]?/g) || [cleaned];
        const chunks = [];
        let current = "";
        for (const sentence of sentences) {{
            const next = (current + " " + sentence.trim()).trim();
            if (next.length > 220 && current) {{
                chunks.push(current);
                current = sentence.trim();
            }} else {{
                current = next;
            }}
        }}
        if (current) chunks.push(current);
        return chunks.slice(0, 14);
    }}

    function stopSpeech(message = "") {{
        queue = [];
        activeIndex = 0;
        if ("speechSynthesis" in window) {{
            window.speechSynthesis.cancel();
        }}
        status.textContent = message;
    }}

    function speakChunk() {{
        if (activeIndex >= queue.length) {{
            status.textContent = "";
            return;
        }}
        const utterance = new SpeechSynthesisUtterance(queue[activeIndex]);
        utterance.lang = lang;
        utterance.rate = 0.86;
        utterance.pitch = 1.04;
        utterance.volume = 1.0;
        const voice = chooseVoice();
        if (voice) utterance.voice = voice;
        utterance.onstart = () => status.textContent = "Speaking softly...";
        utterance.onend = () => {{
            activeIndex += 1;
            window.setTimeout(speakChunk, 140);
        }};
        utterance.onerror = () => stopSpeech("Unable to play voice.");
        window.speechSynthesis.speak(utterance);
    }}

    function speak() {{
        if (!("speechSynthesis" in window)) {{
            status.textContent = "Speech not supported in this browser.";
            return;
        }}
        stopSpeech("");
        queue = speechChunks(answerText);
        activeIndex = 0;
        speakChunk();
    }}

    button.addEventListener("click", speak);
    stopButton.addEventListener("click", () => stopSpeech("Stopped."));
    if (shouldAutoplay) {{
        setTimeout(speak, 450);
    }}
</script>
"""


def _render_header():
    st.markdown(
        """
<div class="app-hero">
    <h1>CSC Mitra</h1>
    <p>Namaste. Ask about CSC services and government schemes in Hindi or English. You will get simple, polite, official-source guidance step by step.</p>
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
    <h2>CSC AI Assistant</h2>
    <p>Your trusted CSC ally</p>
</div>
""",
            unsafe_allow_html=True,
        )
        cloud_consent = True
        response_language = st.selectbox("Response Language", ["Auto", "English", "Hindi"], index=0)

        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_draft = ""
            st.session_state.autoplay_message_id = None
            st.rerun()

        st.divider()
        st.markdown("**Quick Services**")
        for label, prompt in QUICK_PROMPTS:
            if st.button(label, key=f"side_{label}", use_container_width=True):
                side_query = prompt

        st.divider()
        st.markdown(
            """
<div class="sidebar-status">
    🔒 DPDP Compliant<br />
    Verified Official Sources Only
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
    <strong>Add Official Knowledge</strong>
</div>
""",
        unsafe_allow_html=True,
    )

    official_url = st.text_input("Official URL", key="official_ingest_url")
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"], key="official_pdf_upload")

    ingest_col, close_col = st.columns([2, 1])
    with ingest_col:
        if st.button("Ingest Knowledge", type="primary", use_container_width=True):
            if uploaded_pdf:
                status = add_pdf_knowledge(
                    uploaded_pdf,
                    official_url,
                    cloud_consent=cloud_consent,
                    human_reviewed=True,
                )
            elif official_url:
                status = add_knowledge(
                    official_url,
                    cloud_consent=cloud_consent,
                    human_reviewed=True,
                )
            else:
                status = "Add an official URL or choose a PDF first."

            if "failed" in status.lower() or "blocked" in status.lower() or "not" in status.lower():
                st.warning(status)
            else:
                st.success(status)

    with close_col:
        if st.button("Close", use_container_width=True):
            st.session_state.show_ingestion = False
            st.rerun()

    st.divider()
    with st.expander("Human Review Queue", expanded=False):
        pending_reviews = list_pending_reviews(limit=5)
        if not pending_reviews:
            st.caption("No pending human-review items.")
        for item in pending_reviews:
            review_id = item["id"]
            st.markdown(f"**CSC-HITL-{review_id}** · {item['reason']} · confidence {item['confidence']:.2f}")
            st.caption(item["created_at"])
            st.markdown(f"**User query**\n\n{item['query']}")
            if item.get("draft_response"):
                st.markdown(f"**Draft response**\n\n{item['draft_response'][:1200]}")
            if st.button("Mark reviewed", key=f"resolve_hitl_{review_id}"):
                if resolve_review(review_id, operator_note="Reviewed from Streamlit admin panel"):
                    st.success(f"CSC-HITL-{review_id} marked reviewed.")
                    st.rerun()
                else:
                    st.warning("Could not update this review item.")


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

    components.html(
        _browser_speech_html(content, language_code, autoplay=autoplay),
        height=44,
    )

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
    st.session_state.voice_status = "Processing your speech..."

    if voice_mode:
        st.session_state.pending_voice_submit = clean_text
        st.session_state.clear_composer_next = True
    else:
        st.session_state.voice_prefill = clean_text

    st.rerun()


def _render_microphone(voice_language, voice_mode):
    language_code = normalize_voice_language(voice_language, st.session_state.chat_draft)

    if speech_to_text is not None and not whisper_stt_enabled():
        try:
            transcript = speech_to_text(
                language=language_code,
                start_prompt="🎤",
                stop_prompt="🎤 Listening...",
                just_once=True,
                use_container_width=True,
                key="csc_web_speech",
            )
        except TypeError:
            transcript = speech_to_text(
                language=language_code,
                start_prompt="🎤",
                stop_prompt="🎤 Listening...",
                just_once=True,
                key="csc_web_speech",
            )
        if transcript and transcript.strip() != st.session_state.last_voice_transcript:
            _queue_voice_transcript(transcript, voice_mode)
        return

    if whisper_stt_enabled() and mic_recorder is not None:
        try:
            audio = mic_recorder(
                start_prompt="🎤",
                stop_prompt="🎤 Listening...",
                just_once=True,
                use_container_width=True,
                key="csc_whisper_recorder",
            )
        except TypeError:
            audio = mic_recorder(
                start_prompt="🎤",
                stop_prompt="🎤 Listening...",
                just_once=True,
                key="csc_whisper_recorder",
            )
        if audio:
            audio_bytes = audio.get("bytes")
            audio_id = str(audio.get("id") or hash(audio_bytes))
            if audio_id != st.session_state.last_audio_id:
                st.session_state.last_audio_id = audio_id
                with st.spinner("Processing your spoken words..."):
                    transcript, error = transcribe_with_whisper(audio_bytes, voice_language)
                if error:
                    st.session_state.voice_status = ""
                    st.toast("⚠ Voice service busy. Please try again in a few seconds.")
                else:
                    _queue_voice_transcript(transcript, voice_mode)
        return

    if speech_to_text is not None:
        try:
            transcript = speech_to_text(
                language=language_code,
                start_prompt="🎤",
                stop_prompt="🎤 Listening...",
                just_once=True,
                use_container_width=True,
                key="csc_web_speech",
            )
        except TypeError:
            transcript = speech_to_text(
                language=language_code,
                start_prompt="🎤",
                stop_prompt="🎤 Listening...",
                just_once=True,
                key="csc_web_speech",
            )
        if transcript and transcript.strip() != st.session_state.last_voice_transcript:
            _queue_voice_transcript(transcript, voice_mode)
        return

    st.button("🎤", disabled=True, use_container_width=True, help="Microphone input needs streamlit-mic-recorder.")


def _render_composer(voice_language, voice_mode):
    if st.session_state.get("voice_prefill"):
        st.session_state.chat_draft = st.session_state.pop("voice_prefill")
        st.session_state.voice_status = ""

    if st.session_state.get("clear_composer_next"):
        st.session_state.chat_draft = ""
        st.session_state.clear_composer_next = False

    _render_voice_status()

    st.text_area(
        "Ask CSC related question",
        key="chat_draft",
        placeholder="Ask your CSC related question...",
        label_visibility="collapsed",
        height=78,
    )

    admin_visible = _admin_attachment_visible()
    if admin_visible:
        mic_col, mode_col, attach_col, spacer_col, send_col = st.columns([1, 2.2, 1, 5.8, 1], vertical_alignment="center")
    else:
        mic_col, mode_col, spacer_col, send_col = st.columns([1, 2.2, 6.8, 1], vertical_alignment="center")

    with mic_col:
        _render_microphone(voice_language, voice_mode)

    with mode_col:
        mode_label = "🎤 Voice Mode ON" if st.session_state.voice_mode else "🎤 Voice Mode OFF"
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
            "➤",
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

    language_map = {"Auto": "auto", "English": "en", "Hindi": "hi"}
    with st.spinner("Finding a simple, reliable answer for you..."):
        answer = ask(
            clean_query,
            cloud_consent=cloud_consent,
            history=history,
            response_language=language_map[response_language],
            fast_mode=voice_mode,
        )

    assistant_message = _append_message("assistant", answer)
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
st.markdown('<div class="section-label">Popular Services</div>', unsafe_allow_html=True)
quick_query = ""
quick_cols = st.columns(len(QUICK_PROMPTS))
for index, (label, prompt) in enumerate(QUICK_PROMPTS):
    with quick_cols[index]:
        if st.button(label, use_container_width=True):
            quick_query = prompt

st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Recent Questions</div>', unsafe_allow_html=True)
recent_items = "\n".join(f"<div>• {_escape(item)}</div>" for item in _recent_questions())
st.markdown(f'<div class="recent-list">{recent_items}</div>', unsafe_allow_html=True)

if st.session_state.messages:
    st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
_render_chat_history(response_language, voice_mode)
st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)
submitted_query = sidebar_query or quick_query or _render_composer(voice_language, voice_mode)
_render_ingestion_panel(cloud_consent)

if submitted_query:
    _build_answer(submitted_query, cloud_consent, response_language, voice_mode)
