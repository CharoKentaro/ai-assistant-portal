# tools/calendar_tool.py

import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz
from streamlit_mic_recorder import mic_recorder
import time

# ===============================================================
# 補助関数（Speech-to-Textも、カレンダーURL生成も、両方とも必要）
# ===============================================================
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    try:
        client_options = ClientOptions(api_key=api_key)
        client = speech.SpeechClient(client_options=client_options)
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(language_code="ja-JP", model="latest_long")
        response = client.recognize(config=config, audio=audio)
        if response.results: return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識エラー: {e}")
    return None

def create_google_calendar_url(details):
    try:
        jst = pytz.timezone('Asia/Tokyo')
        start_time_jst = jst.localize(datetime.fromisoformat(details['start_time']))
        end_time_jst = jst.localize(datetime.fromisoformat(details['end_time']))
        start_time_utc = start_time_jst.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
        end_time_utc = end_time_jst.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
        dates = f"{start_time_utc}/{end_time_utc}"
    except (ValueError, KeyError): dates = ""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {"text": details.get('title', ''), "dates": dates, "location": details.get('location', ''), "details": details.get('details', '')}
    return f"{base_url}&{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

# ===============================================================
# 専門家のメインの仕事（ハイブリッド戦略）
# ===============================================================
def show_tool(gemini_api_key, speech_api_key):
    st.header("📅 あなただけのAI秘書", divider='rainbow')

    # --- 状態管理の初期化 ---
    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！ご予定を、下の方法でお伝えください。"}]
    # 「こだま」防止用のID記憶場所
    if "cal_last_mic_id" not in st.session_state:
        st.session_state.cal_last_mic_id = None

    # --- チャット履歴の表示 ---
    for message in st.session_state.cal_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- 共通AI処理関数 ---
    def process_with_gemini(prompt_text):
        with st.chat_message("user"):
            st.markdown(prompt_text)
        st.session_state.cal_messages.append({"role": "user", "content": prompt_text})

        with st.chat_message("assistant"):
            if not gemini_api_key:
                st.error("サイドバーでGemini APIキーを設定してください。")
                return

            try:
                with st.spinner("AIが予定を組み立てています..."):
                    genai.configure(api_key=gemini_api_key)
                    jst = pytz.timezone('Asia/Tokyo')
                    current_time_jst = datetime.now(jst).isoformat()
                    
                    system_prompt = f"""
                    あなたは予定を解釈する優秀なアシスタントです。ユーザーのテキストから「title」「start_time」「end_time」「location」「details」を抽出してください。
                    - 現在の日時は `{current_time_jst}` (JST)です。これを基準に日時を解釈してください。
                    - 日時は `YYYY-MM-DDTHH:MM:SS` 形式で出力してください。
                    - `end_time` が不明な場合は、`start_time` の1時間後を自動設定してください。
                    - 必ず以下のJSON形式のみで回答してください。他の言葉は一切含めないでください。
                    ```json
                    {{ "title": "（件名）", "start_time": "YYYY-MM-DDTHH:MM:SS", "end_time": "YYYY-MM-DDTHH:MM:SS", "location": "（場所）", "details": "（詳細）" }}
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content(prompt_text)
                    json_text = response.text.strip().lstrip("```json").rstrip("```").strip()
                    schedule_details = json.loads(json_text)
                    calendar_url = create_google_calendar_url(schedule_details)
                    
                    display_start_time = "未設定"
                    if schedule_details.get('start_time'):
                        try: display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y年%m月%d日 %H:%M')
                        except: display_start_time = "AIが日付の解析に失敗"

                    ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。\n\n- **件名:** {schedule_details.get('title', '未設定')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', '未設定')}\n- **詳細:** {schedule_details.get('details', '未設定')}\n\n[📅 Googleカレンダーにこの予定を追加する]({calendar_url})"""
                    st.markdown(ai_response)
                    st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})

            except Exception as e:
                error_message = f"AIとの通信中にエラーが発生しました: {e}"
                st.error(error_message)
                st.session_state.cal_messages.append({"role": "assistant", "content": "申し訳ありません、エラーが発生しました。"})


    # --- ★★★ ここからが、ハイブリッド戦略の、核心部です ★★★ ---

    # --- 第一の道（成功確率100%）：テキスト入力 ---
    st.write("---")
    st.write("##### 方法１：キーボードで入力する（最も確実です）")
    text_prompt = st.chat_input("キーボードで予定を入力...", key="cal_text_input")
    if text_prompt:
        process_with_gemini(text_prompt)

    # --- 第二の道（挑戦確率90%）：音声入力 ---
    st.write("---")
    st.write("##### 方法２：音声で入力する（ベータ版）")
    
    col1, col2 = st.columns(2)
    with col1:
        # マイク入力
        audio_info = mic_recorder(start_prompt="🎤 マイクで録音", stop_prompt="⏹️ 停止", key='cal_mic_recorder')
        if audio_info and audio_info['id'] != st.session_state.cal_last_mic_id:
            st.session_state.cal_last_mic_id = audio_info['id'] # IDを記憶
            if not speech_api_key:
                st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
            else:
                with st.spinner("音声を文字に変換中..."):
                    transcript = transcribe_audio(audio_info['bytes'], speech_api_key)
                    if transcript:
                        process_with_gemini(transcript)

    with col2:
        # ファイルアップロード
        uploaded_file = st.file_uploader("📁 音声ファイルをアップロード", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
        if uploaded_file:
            # ファイルがアップロードされたら、それを即座に処理する
            if not speech_api_key:
                st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
            else:
                with st.spinner("音声ファイルを文字に変換中..."):
                     transcript = transcribe_audio(uploaded_file.getvalue(), speech_api_key)
                     if transcript:
                         process_with_gemini(transcript)
