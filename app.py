import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz

# --- アプリの基本設定 ---
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")
st.title("🤖 AIアシスタント・ポータル")
st.caption("あなたの業務をAIがサポートします (Powered by Google Cloud)")

# --- サイドバー：APIキー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    gemini_api_key = st.text_input("1. Gemini APIキー", type="password", help="Google AI Studioで取得した、AIと会話するためのキーを貼り付けてください。")
    speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", help="Google Cloud Platformで取得した、音声を文字に変換するためのキーを貼り付けてください。")
    st.divider()
    st.markdown("""
    <div style="font-size: 0.9em;">
    <a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得はこちら</a><br>
    <a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得はこちら</a>
    </div>
    """, unsafe_allow_html=True)

# --- Google Speech-to-Text APIを叩く関数 ---
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    client_options = ClientOptions(api_key=api_key)
    client = speech.SpeechClient(client_options=client_options)
    audio = speech.RecognitionAudio(content=audio_bytes)
    # 様々な音声ファイル形式に対応できるよう、エンコーディング指定を削除
    config = speech.RecognitionConfig(sample_rate_hertz=48000, language_code="ja-JP", audio_channel_count=1) # チャンネル数を1に指定
    try:
        response = client.recognize(config=config, audio=audio)
        if response.results: return response.results[0].alternatives[0].transcript
    except Exception as e:
        # エラーメッセージをより具体的に
        st.error(f"音声認識でエラーが発生しました。ファイルの形式がサポートされていない可能性があります。: {e}")
    return None

# --- GoogleカレンダーURL生成関数 (変更なし) ---
def create_google_calendar_url(details):
    try:
        jst = pytz.timezone('Asia/Tokyo'); start_time_naive = datetime.fromisoformat(details['start_time']); end_time_naive = datetime.fromisoformat(details['end_time']); start_time_jst = jst.localize(start_time_naive); end_time_jst = jst.localize(end_time_naive); start_time_utc = start_time_jst.astimezone(pytz.utc); end_time_utc = end_time_jst.astimezone(pytz.utc); start_time_str = start_time_utc.strftime('%Y%m%dT%H%M%SZ'); end_time_str = end_time_utc.strftime('%Y%m%dT%H%M%SZ'); dates = f"{start_time_str}/{end_time_str}"
    except (ValueError, KeyError): dates = ""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"; params = { "text": details.get('title', ''), "dates": dates, "location": details.get('location', ''), "details": details.get('details', '') }; encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote); return f"{base_url}&{encoded_params}"

# --- セッションステートの初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}]

# --- メイン画面 ---
st.header("📅 AIカレンダー秘書")
st.info("テキストで直接入力するか、音声ファイルをアップロードしてAIに伝えてください。")

# --- チャット履歴の表示 ---
for message in st.session_state.messages:
    role = "model" if message["role"] == "assistant" else message["role"]
    with st.chat_message(role):
        st.markdown(message["content"])

# --- 入力部分 ---
prompt = None

# 音声ファイルアップロード機能
uploaded_file = st.file_uploader("ボイスメモなどの音声ファイルをアップロード:", type=['wav', 'mp3', 'm4a', 'flac'])
if uploaded_file is not None:
    if not speech_api_key:
        st.error("サイドバーにSpeech-to-Text APIキーを入力してください。")
    else:
        with st.spinner("音声ファイルを文字に変換中..."):
            audio_bytes = uploaded_file.getvalue()
            transcript = transcribe_audio(audio_bytes, speech_api_key)
            if transcript:
                prompt = transcript
            else:
                st.warning("音声の認識に失敗しました。")

# テキスト入力
text_prompt = st.chat_input("または、キーボードで入力...")
if text_prompt:
    prompt = text_prompt

# --- チャット処理 ---
if prompt:
    if not gemini_api_key: st.error("サイドバーにGemini APIキーを入力してください。"); st.stop()
    
    # ユーザーの発言をチャットに追加
    st.session_state.messages.append({"role": "user", "content": prompt});
    with st.chat_message("user"): st.markdown(prompt)

    try:
        genai.configure(api_key=gemini_api_key)
        jst = pytz.timezone('Asia/Tokyo')
        current_time_jst = datetime.now(jst).isoformat()
        
        # あなたの指摘を反映した、より丁寧なプロンプト
        system_prompt = f"""
        あなたは、ユーザーから渡されたテキスト（キーボード入力、または音声入力を文字起こししたもの）を解釈し、Googleカレンダーの予定を作成する情報を抽出する、非常に優秀なアシスタントです。
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
                if schedule_details.get('start_time'): display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M:%S')
                ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。\n\n- **件名:** {schedule_details.get('title', '未設定')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', '未設定')}\n- **詳細:** {schedule_details.get('details', '未設定')}\n\n[📅 Googleカレンダーにこの予定を追加する]({calendar_url})"""
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

    except Exception as e:
        st.error(f"エラーが発生しました: {e}"); st.session_state.messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})
