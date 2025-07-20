import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz

# --- 補助関数 (変更なし) ---
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    try:
        client = speech.SpeechClient(client_options=ClientOptions(api_key=api_key))
        audio, config = speech.RecognitionAudio(content=audio_bytes), speech.RecognitionConfig(language_code="ja-JP")
        response = client.recognize(config=config, audio=audio)
        if response.results: return response.results[0].alternatives[0].transcript
    except Exception as e: st.error(f"音声認識エラー: {e}")
    return None

def create_google_calendar_url(details):
    try:
        jst = pytz.timezone('Asia/Tokyo'); start_time_naive, end_time_naive = datetime.fromisoformat(details['start_time']), datetime.fromisoformat(details['end_time']); start_time_jst, end_time_jst = jst.localize(start_time_naive), jst.localize(end_time_naive); start_time_utc, end_time_utc = start_time_jst.astimezone(pytz.utc), end_time_jst.astimezone(pytz.utc)
        dates = f"{start_time_utc.strftime('%Y%m%dT%H%M%SZ')}/{end_time_utc.strftime('%Y%m%dT%H%M%SZ')}"
    except: dates = ""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"; params = { "text": details.get('title', ''), "dates": dates, "location": details.get('location', ''), "details": details.get('details', '') }
    return f"{base_url}&{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

# ===============================================================
# 専門家のメインの仕事
# ===============================================================
def show_tool(gemini_api_key, speech_api_key): # 司令塔からAPIキーを受け取る
    
    # このツールは、もはやAPIキーの管理について、一切知る必要がありません。
    # ただ、与えられた道具を使って、最高の仕事をするだけです。

    # --- メインのチャットUI ---
    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！ご予定を何なりとお申し付けください。"}]
    
    for message in st.session_state.cal_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = None
    uploaded_file = st.file_uploader("音声ファイルをアップロード:", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
    if uploaded_file:
        if not speech_api_key:
            st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
        else:
            with st.spinner("音声ファイルを文字に変換中..."):
                transcript = transcribe_audio(uploaded_file.getvalue(), speech_api_key)
                if transcript:
                    prompt = transcript
                else:
                    st.warning("音声の認識に失敗しました。")
    
    if text_prompt := st.chat_input("または、キーボードで入力..."):
        prompt = text_prompt

    if prompt:
        if not gemini_api_key:
            st.error("サイドバーでGemini APIキーを設定してください。")
            st.stop()
        
        st.session_state.cal_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            genai.configure(api_key=gemini_api_key)
            current_time_jst = datetime.now(pytz.timezone('Asia/Tokyo')).isoformat()
            system_prompt = f"""
            あなたは、ユーザーから渡されたテキストを解釈し、Googleカレンダーの予定を作成する情報を抽出する、非常に優秀なアシスタントです。
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
                    schedule_details = json.loads(response.text.strip().lstrip("```json").rstrip("```"))
                    calendar_url = create_google_calendar_url(schedule_details)
                    display_start_time = "未設定"
                    if t := schedule_details.get('start_time'):
                        display_start_time = datetime.fromisoformat(t).strftime('%Y-%m-%d %H:%M')
                    ai_response = f"""以下の内容で承りました。\n\n- **件名:** {schedule_details.get('title', 'N/A')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', 'N/A')}\n- **詳細:** {schedule_details.get('details', 'N/A')}\n\n[📅 Googleカレンダーに追加]({calendar_url})"""
                    st.markdown(ai_response)
                    st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})
        except Exception as e:
            st.error(f"エラー: {e}")
            st.session_state.cal_messages.append({"role": "assistant", "content": f"エラーが発生しました。({e})"})
