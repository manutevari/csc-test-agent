import hmac
import html
import json

import streamlit as st
import streamlit.components.v1 as components

from knowledge import add_knowledge, index_csc_service_guides
from mas_engine import ask
from voice_assistant import (
    configured_secret,
    normalize_voice_language,
    openai_audio_enabled,
    synthesize_with_openai,
    transcribe_with_whisper,
)

try:
    from streamlit_mic_recorder import mic_recorder, speech_to_text
except Exception:
    mic_recorder = None
    speech_to_text = None


st.set_page_config(
    page_title="CSC AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


QUICK_PROMPTS = (
    ("PM Kisan", "PM Kisan registration ka process batao"),
    ("PAN", "PAN correction process batao"),
    ("DigiPay", "How to use DigiPay for cash withdrawal"),
    ("e-Shram", "e-Shram registration ke liye documents kya hain"),
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
        --muted: #64748b;
        --line: #e5e7eb;
        --panel: #ffffff;
        --soft: #f4f7fb;
    }

    html, body, [class*="css"], .stMarkdown, .stTextInput, .stTextArea, .stButton, .stSelectbox {
        font-family: Inter, "Noto Sans Devanagari", "Nirmala UI", "Mangal", system-ui, sans-serif;
    }

    .stApp {
        background: #f8fafc;
        color: var(--ink);
    }

    .block-container {
        max-width: 1040px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: #f1f5f9;
        border-right: 1px solid var(--line);
    }

    .app-hero {
        align-items: center;
        background: linear-gradient(135deg, #ffffff 0%, #f7fbff 55%, #fff7ed 100%);
        border: 1px solid var(--line);
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        gap: 20px;
        margin-bottom: 16px;
        padding: 18px 20px;
    }

    .app-hero h1 {
        color: var(--ink);
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: 0;
        line-height: 1.16;
        margin: 0 0 6px 0;
    }

    .app-hero p {
        color: var(--muted);
        font-size: .96rem;
        line-height: 1.5;
        margin: 0;
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
        border-color: #d7dde8 !important;
        min-height: 76px !important;
    }

    .stButton > button {
        border-radius: 8px;
        min-height: 42px;
        font-weight: 750;
    }

    .stButton > button[kind="primary"] {
        background: var(--csc-blue);
        border-color: var(--csc-blue);
    }

    .empty-state {
        background: var(--panel);
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        color: var(--muted);
        padding: 28px 20px;
        text-align: center;
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
<button id="listenBtn" type="button" aria-label="Listen to assistant response">🔊 Listen</button>
<span id="listenStatus" aria-live="polite"></span>
<style>
    body {{
        margin: 0;
        background: transparent;
        font-family: Inter, system-ui, sans-serif;
    }}
    #listenBtn {{
        align-items: center;
        background: #ffffff;
        border: 1px solid #d6dde8;
        border-radius: 8px;
        color: #102033;
        cursor: pointer;
        display: inline-flex;
        font-size: 13px;
        font-weight: 750;
        gap: 6px;
        min-height: 34px;
        padding: 7px 11px;
    }}
    #listenBtn:hover {{
        border-color: #005bac;
        color: #005bac;
    }}
    #listenStatus {{
        color: #64748b;
        font-size: 12px;
        margin-left: 8px;
    }}
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
            status.textContent = "Speech not supported in this browser.";
            return;
        }}
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(answerText);
        utterance.lang = lang;
        utterance.rate = 0.88;
        utterance.pitch = 1.03;
        utterance.volume = 1.0;
        const voice = chooseVoice();
        if (voice) utterance.voice = voice;
        utterance.onstart = () => status.textContent = "Speaking...";
        utterance.onend = () => status.textContent = "";
        utterance.onerror = () => status.textContent = "Unable to play voice.";
        window.speechSynthesis.speak(utterance);
    }}

    button.addEventListener("click", speak);
    if (shouldAutoplay) {{
        setTimeout(speak, 450);
    }}
</script>
"""


def _admin_secret():
    return configured_secret("CSC_ADMIN_PASSWORD", "ADMIN_PASSWORD", "ADMIN_PIN")


def _render_header():
    st.markdown(
        """
<div class="app-hero">
    <div>
        <h1>CSC AI Assistant</h1>
        <p>Chat or speak in Hindi and English for CSC service guidance with official-source guardrails.</p>
    </div>
    <div class="hero-badges">
        <span class="hero-badge">Voice input</span>
        <span class="hero-badge">Voice output</span>
        <span class="hero-badge">Admin-only ingestion</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_sidebar():
    with st.sidebar:
        st.header("Voice")
        cloud_consent = True
        voice_mode = st.toggle(
            "Voice conversation mode",
            key="voice_mode",
            help="When on, transcribed speech is sent automatically and the assistant reads the answer aloud.",
        )
        voice_language = st.selectbox("Voice language", ["Auto", "Hindi", "English"], index=0)
        response_language = st.selectbox("Response language", ["Auto", "English", "Hindi"], index=0)

        if openai_audio_enabled() and mic_recorder is not None:
            st.caption("Speech input: OpenAI Whisper. Voice output: browser speech plus optional OpenAI MP3.")
        elif speech_to_text is not None:
            st.caption("Speech input: browser Web Speech API. Voice output: browser speech synthesis.")
        else:
            st.warning("Install streamlit-mic-recorder to enable microphone input.")

        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_draft = ""
            st.session_state.tts_audio = {}
            st.session_state.autoplay_message_id = None
            st.rerun()

        st.divider()
        _render_admin_tools(cloud_consent)

        st.divider()
        st.caption("Try: PM Kisan status, PAN correction, DigiPay, Ayushman Bharat, e-Shram registration.")

    return cloud_consent, response_language, voice_language, voice_mode


def _render_admin_tools(cloud_consent):
    st.header("Admin")
    admin_password = _admin_secret()
    if not admin_password:
        st.caption("Set CSC_ADMIN_PASSWORD in Streamlit secrets to enable knowledge ingestion.")
        return

    if not st.session_state.admin_unlocked:
        entered = st.text_input("Admin password", type="password")
        if st.button("Unlock admin tools", use_container_width=True):
            if hmac.compare_digest(entered or "", admin_password):
                st.session_state.admin_unlocked = True
                st.success("Admin tools unlocked.")
                st.rerun()
            else:
                st.error("Invalid admin password.")
        return

    st.success("Admin tools unlocked.")
    if st.button("Lock admin tools", use_container_width=True):
        st.session_state.admin_unlocked = False
        st.rerun()

    st.subheader("Knowledge Ingestion")
    source_reviewed = st.checkbox(
        "I reviewed the source and approve storing embeddings",
        value=False,
        help="Only verified official CSC/service URLs should be ingested.",
    )
    url_input = st.text_input("Paste CSC or official service URL")
    can_store = source_reviewed

    if st.button("Add Knowledge", use_container_width=True, disabled=not can_store):
        if url_input:
            status = add_knowledge(
                url_input,
                cloud_consent=cloud_consent,
                human_reviewed=source_reviewed,
            )
            if "failed" not in status.lower() and "not stored" not in status.lower() and "blocked" not in status.lower():
                st.success(status)
            else:
                st.warning(status)
        else:
            st.warning("Paste an allowed CSC or official service URL first.")

    if st.button("Index CSC service guides", use_container_width=True, disabled=not can_store):
        status = index_csc_service_guides(
            cloud_consent=cloud_consent,
            human_reviewed=source_reviewed,
        )
        if "failed" not in status.lower() and "not indexed" not in status.lower() and "not granted" not in status.lower():
            st.success(status)
        else:
            st.warning(status)


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
        openai_col, browser_col = st.columns([1, 3])
        with openai_col:
            if st.button("🔊 MP3", key=f"openai_{tts_key}", help="Generate natural voice with OpenAI TTS."):
                with st.spinner("Preparing voice..."):
                    audio, error = synthesize_with_openai(content, response_language)
                if error:
                    st.warning(error)
                else:
                    st.session_state.tts_audio[tts_key] = audio

        if tts_key in st.session_state.tts_audio:
            st.audio(st.session_state.tts_audio[tts_key], format="audio/mp3")

        with browser_col:
            components.html(
                _browser_speech_html(content, language_code, autoplay=autoplay),
                height=42,
            )
    else:
        components.html(
            _browser_speech_html(content, language_code, autoplay=autoplay),
            height=42,
        )

    if autoplay:
        st.session_state.autoplay_message_id = None


def _render_chat_history(response_language, voice_mode):
    if not st.session_state.messages:
        st.markdown(
            """
<div class="empty-state">
    Ask a CSC related question, use the microphone, or choose a popular prompt.
</div>
""",
            unsafe_allow_html=True,
        )
        return

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_listen_control(message, response_language, voice_mode)


def _queue_voice_transcript(transcript, voice_mode):
    clean_text = (transcript or "").strip()
    if not clean_text:
        return

    st.session_state.last_voice_transcript = clean_text
    st.session_state.voice_status = "Processing Speech..."

    if voice_mode:
        st.session_state.pending_voice_submit = clean_text
        st.session_state.clear_composer_next = True
    else:
        st.session_state.voice_prefill = clean_text

    st.rerun()


def _render_microphone(voice_language, voice_mode):
    language_code = normalize_voice_language(voice_language, st.session_state.chat_draft)

    if openai_audio_enabled() and mic_recorder is not None:
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
                with st.spinner("⚙️ Processing Speech..."):
                    transcript, error = transcribe_with_whisper(audio_bytes, voice_language)
                if error:
                    st.warning(error)
                    st.session_state.voice_status = ""
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

    input_col, mic_col, attach_col, send_col = st.columns([8, 1, 1, 1], vertical_alignment="bottom")
    with input_col:
        st.text_area(
            "Ask CSC related question",
            key="chat_draft",
            placeholder="Ask CSC related question...",
            label_visibility="collapsed",
            height=78,
        )

    with mic_col:
        _render_microphone(voice_language, voice_mode)

    with attach_col:
        st.button(
            "📎",
            disabled=True,
            use_container_width=True,
            help="Knowledge uploads are admin-only through the sidebar ingestion tools.",
        )

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
    with st.spinner("Processing..."):
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
cloud_consent, response_language, voice_language, voice_mode = _render_sidebar()
_render_header()

quick_query = ""
quick_cols = st.columns(len(QUICK_PROMPTS))
for index, (label, prompt) in enumerate(QUICK_PROMPTS):
    with quick_cols[index]:
        if st.button(label, use_container_width=True):
            quick_query = prompt

_render_chat_history(response_language, voice_mode)
submitted_query = quick_query or _render_composer(voice_language, voice_mode)

if submitted_query:
    _build_answer(submitted_query, cloud_consent, response_language, voice_mode)
