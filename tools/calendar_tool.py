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
# 補助関数（変更なし）
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
# 専門家のメインの仕事
# ===============================================================
def show_tool(gemini_api_key, speech_api_key):
    st.header("📅 あなただけのAI秘書", divider='rainbow')

    # セッション状態の初期化
    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！ご予定を、下の３つの方法のいずれかでお伝えください。"}]
    if "new_prompt_to_process" not in st.session_state:
        st.session_state.new_prompt_to_process = None
    if "processing_audio" not in st.session_state:
        st.session_state.processing_audio = False
    if "audio_processed" not in st.session_state:
        st.session_state.audio_processed = False

    # --- チャット履歴の表示 ---
    for message in st.session_state.cal_messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])

    # AI処理が完了した直後の状態クリア
    if st.session_state.new_prompt_to_process is None and st.session_state.audio_processed:
        st.session_state.audio_processed = False
        st.session_state.processing_audio = False

    # ★ 1. 入力受付：処理すべきタスクが無い場合のみ、入力を受け付ける
    if st.session_state.new_prompt_to_process is None and not st.session_state.processing_audio:
        st.write("---")
        st.write("##### 方法１：マイクで直接話す")
        audio_info = mic_recorder(start_prompt="🎤 録音開始", stop_prompt="⏹️ 録音停止", key='cal_mic_recorder')
        if audio_info and audio_info['bytes'] and not st.session_state.processing_audio:
            if not speech_api_key: 
                st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
            else:
                st.session_state.processing_audio = True
                with st.spinner("音声を文字に変換中..."):
                    transcript = transcribe_audio(audio_info['bytes'], speech_api_key)
                    if transcript:
                        st.session_state.new_prompt_to_process = transcript
                        st.session_state.audio_processed = True
                        st.rerun()
                    else:
                        st.session_state.processing_audio = False

        st.write("---")
        st.write("##### 方法２：音声ファイルをアップロードする")
        uploaded_file = st.file_uploader("音声ファイルを選択:", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
        if uploaded_file and not st.session_state.processing_audio:
            if not speech_api_key: 
                st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
            else:
                st.session_state.processing_audio = True
                with st.spinner("音声ファイルを文字に変換中..."):
                    transcript = transcribe_audio(uploaded_file.getvalue(), speech_api_key)
                    if transcript:
                        st.session_state.new_prompt_to_process = transcript
                        st.session_state.audio_processed = True
                        st.rerun()
                    else:
                        st.session_state.processing_audio = False

        st.write("---")
        # テキスト入力は音声処理中でない場合のみ有効
        if not st.session_state.processing_audio:
            text_prompt = st.chat_input("方法３：キーボードで入力...", key="cal_text_input")
            if text_prompt:
                st.session_state.new_prompt_to_process = text_prompt
                st.rerun()

    # ★ 2. AI処理ブロック：処理すべきタスクがある場合のみ、実行する
    if st.session_state.new_prompt_to_process:
        prompt = st.session_state.new_prompt_to_process
        st.session_state.cal_messages.append({"role": "user", "content": prompt})
        
        # ユーザープロンプトを再描画するために、一度リロードを挟む
        if "user_prompt_displayed" not in st.session_state:
            st.session_state.user_prompt_displayed = True
            st.rerun()
        
        with st.chat_message("assistant"):
            if not gemini_api_key: 
                st.error("サイドバーでGemini APIキーを設定してください。")
            else:
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
                        {{
                          "title": "（件名）", "start_time": "YYYY-MM-DDTHH:MM:SS", "end_time": "YYYY-MM-DDTHH:MM:SS", "location": "（場所）", "details": "（詳細）"
                        }}
                        ```
                        """
                        model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                        response = model.generate_content(prompt)
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
                    error_message = f"AIとの通信中にエラー: {e}"
                    st.error(error_message)
                    st.session_state.cal_messages.append({"role": "assistant", "content": "申し訳ありません、エラーが発生しました。"})
            
            # ★ 3. 処理が完了したら、タスクを記憶から消し、表示フラグもリセットして、次の入力に備える
            st.session_state.new_prompt_to_process = None
            if "user_prompt_displayed" in st.session_state:
                del st.session_state.user_prompt_displayed
            # 音声処理フラグはここでは直接リセットしない（次回の描画時にクリア）
            st.rerun()
