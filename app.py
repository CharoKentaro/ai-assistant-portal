import streamlit as st
import google.generativeai as genai
from google.cloud import speech
import json
from datetime import datetime
import urllib.parse
import pytz
import os
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings
import base64

# --- 認証情報の設定 ---
# StreamlitのSecrets機能からサービスアカウントキーを読み込む
# この部分は、後ほど設定する「秘密の鍵」で動作します
try:
    # st.secretsは辞書形式なので、直接JSON文字列に変換する
    creds_json_str = json.dumps(st.secrets["gcp_service_account"])
    # Base64エンコードして環境変数に設定するのが、より安全な方法
    encoded_creds = base64.b64encode(creds_json_str.encode()).decode()
    os.environ["GCP_CREDENTIALS_BASE64"] = encoded_creds
except (FileNotFoundError, KeyError):
    st.error("GCPのサービスアカウント認証情報が設定されていません。")
    st.stop()

# --- Google Speech-to-Text APIを叩く関数 ---
# 認証情報をデコードしてクライアントを初期化
def get_speech_client():
    try:
        encoded_creds = os.environ.get("GCP_CREDENTIALS_BASE64")
        if not encoded_creds:
            return None
        decoded_creds = base64.b64decode(encoded_creds)
        creds_json = json.loads(decoded_creds)
        
        # from_service_account_info を使用して認証情報を直接渡す
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(creds_json)
        client = speech.SpeechClient(credentials=credentials)
        return client
    except Exception as e:
        st.error(f"認証クライアントの初期化中にエラー: {e}")
        return None

def transcribe_audio(audio_frames, speech_client):
    if not audio_frames or not speech_client:
        return None
    
    audio_bytes = b"".join(frame.to_ndarray().tobytes() for frame in audio_frames)
    
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=48000,
        language_code="ja-JP",
    )
    
    try:
        response = speech_client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識でエラーが発生しました: {e}")
    return None

# --- アプリの基本設定 ---
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")
st.title("🤖 AIアシスタント・ポータル")
st.caption("あなたの業務をAIがサポートします (Powered by Google Cloud)")

# --- サイドバー：APIキー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    gemini_api_key = st.text_input("Gemini APIキー (Google AI Studio)", type="password")
    st.markdown("""
    <div style="font-size: 0.9em;">
    <a href="https://aistudio.google.com/app/apikey" target="_blank">Gemini APIキーの取得はこちら</a>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div style="font-size: 0.8em;">
    <strong>このアプリについて</strong><br>
    入力されたAPIキーや会話内容は、サーバーに一切保存されません。
    </div>
    """, unsafe_allow_html=True)

# --- GoogleカレンダーURL生成関数 ---
def create_google_calendar_url(details):
    try:
        jst = pytz.timezone('Asia/Tokyo')
        start_time_naive = datetime.fromisoformat(details['start_time'])
        end_time_naive = datetime.fromisoformat(details['end_time'])
        start_time_jst = jst.localize(start_time_naive)
        end_time_jst = jst.localize(end_time_naive)
        start_time_utc = start_time_jst.astimezone(pytz.utc)
        end_time_utc = end_time_jst.astimezone(pytz.utc)
        start_time_str = start_time_utc.strftime('%Y%m%dT%H%M%SZ')
        end_time_str = end_time_utc.strftime('%Y%m%dT%H%M%SZ')
        dates = f"{start_time_str}/{end_time_str}"
    except (ValueError, KeyError):
        dates = ""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {
        "text": details.get('title', ''),
        "dates": dates,
        "location": details.get('location', ''),
        "details": details.get('details', '')
    }
    encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{base_url}&{encoded_params}"


# --- メイン画面 ---
st.header("📅 AIカレンダー秘書")
st.info("下のタブで入力方法を選んで、AIに話しかけてみてください。")

# --- チャット履歴の表示 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}]

for message in st.session_state.messages:
    role = "model" if message["role"] == "assistant" else message["role"]
    with st.chat_message(role):
        st.markdown(message["content"])

# --- 入力部分 ---
prompt = None
tab1, tab2 = st.tabs(["🎙️ 音声で入力", "⌨️ キーボードで入力"])

with tab1:
    webrtc_ctx = webrtc_streamer(
        key="speech-to-text",
        mode=WebRtcMode.SEND_ONLY,
        audio_receiver_size=1024,
        client_settings=ClientSettings(
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
            media_stream_constraints={"video": False, "audio": True},
        ),
    )

    if st.button("この音声で決定"):
        if webrtc_ctx.audio_receiver:
            speech_client = get_speech_client()
            if speech_client:
                audio_frames = webrtc_ctx.audio_receiver.get_frames()
                with st.spinner("音声を文字に変換中..."):
                    transcript = transcribe_audio(audio_frames, speech_client)
                    if transcript:
                        st.session_state.last_transcript = transcript
                        st.rerun()
                    else:
                        st.warning("音声を認識できませんでした。もう一度お試しください。")
            else:
                st.error("音声認識サービスの準備ができていません。")
        else:
            st.warning("まずマイクで録音を開始してください。")

if "last_transcript" in st.session_state and st.session_state.last_transcript:
    prompt = st.session_state.last_transcript
    st.session_state.last_transcript = None

with tab2:
    text_prompt = st.chat_input("予定を入力してください...")
    if text_prompt:
        prompt = text_prompt


# --- チャット処理 ---
if prompt:
    if not gemini_api_key:
        st.error("サイドバーにGemini APIキーを入力してください。")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        genai.configure(api_key=gemini_api_key)
        
        jst = pytz.timezone('Asia/Tokyo')
        current_time_jst = datetime.now(jst).isoformat()
        
        system_prompt = f"""
        あなたは、自然言語からGoogleカレンダーの予定を作成するための情報を抽出する、非常に優秀なアシスタントです。
        ユーザーのテキストから「title (件名)」「start_time (開始日時)」「end_time (終了日時)」「location (場所)」「details (詳細説明)」を抽出してください。
        - 現在の日時は `{current_time_jst}` です。これは日本標準時(JST)です。この日時を基準に「明日」「来週」などを解釈してください。
        - 日時は必ず `YYYY-MM-DDTHH:MM:SS` というISO 8601形式で出力してください。
        - `end_time` が不明な場合は、`start_time` の1時間後を自動的に設定してください。
        - 抽出した情報は、必ず以下のJSON形式のみで回答してください。他の言葉は一切含めないでください。
        ```json
        {{
          "title": "（ここに件名）",
          "start_time": "YYYY-MM-DDTHH:MM:SS",
          "end_time": "YYYY-MM-DDTHH:MM:SS",
          "location": "（ここに場所）",
          "details": "（ここに詳細）"
        }}
        ```
        """
        
        model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)

        with st.chat_message("assistant"):
            with st.spinner("AIが予定を組み立てています..."):
                response = model.generate_content(prompt)
                
                json_text = response.text.strip().lstrip("```json").rstrip("```")
                schedule_details = json.loads(json_text)
                
                calendar_url = create_google_calendar_url(schedule_details)
                
                display_start_time = "未設定"
                if schedule_details.get('start_time'):
                    display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M:%S')

                ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。

- **件名:** {schedule_details.get('title', '未設定')}
- **日時:** {display_start_time}
- **場所:** {schedule_details.get('location', '未設定')}
- **詳細:** {schedule_details.get('details', '未設定')}

[📅 Googleカレンダーにこの予定を追加する]({calendar_url})
"""
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.session_state.messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})
