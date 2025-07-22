# tools/calendar_tool.py

import streamlit as st
import google.generativeai as genai
# Speech-to-Text関連のライブラリは、全て不要になった！
import json
from datetime import datetime
import urllib.parse
import pytz
from streamlit_mic_recorder import mic_recorder
import time

# ===============================================================
# 補助関数（transcribe_audioは完全に不要に）
# ===============================================================
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
def show_tool(gemini_api_key, speech_api_key): # speech_api_keyはもう使わないが、互換性のために残す
    st.header("📅 あなただけのAI秘書", divider='rainbow')

    # --- 状態管理の初期化 ---
    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！ご予定を、キーボードかマイクで直接お伝えください。"}]
    if "cal_task" not in st.session_state:
        st.session_state.cal_task = None
        st.session_state.cal_task_type = None

    # --- チャット履歴の表示 ---
    for message in st.session_state.cal_messages:
        # ユーザーメッセージが音声の場合の表示を調整
        if message["role"] == "user" and isinstance(message["content"], dict) and "type" in message["content"]:
            with st.chat_message("user"):
                st.write("🎤 (音声で伝えました)")
        else:
             with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # --- 「待機フェーズ」の定義 ---
    if st.session_state.cal_task is None:
        # UIの定義
        st.write("---")
        text_prompt = st.chat_input("キーボードで入力...", key="cal_text_input")
        audio_info = mic_recorder(start_prompt="🎤 マイクで録音", stop_prompt="⏹️ 停止", key='cal_mic_recorder')

        # いずれかの入力があったら、タスクとして記憶し、リロード
        if text_prompt:
            st.session_state.cal_task = text_prompt
            st.session_state.cal_task_type = "text"
            st.session_state.cal_messages.append({"role": "user", "content": text_prompt})
            st.rerun()
        elif audio_info and audio_info['bytes']:
            st.session_state.cal_task = audio_info['bytes']
            st.session_state.cal_task_type = "audio"
            # ユーザーの入力として「音声」を記録
            st.session_state.cal_messages.append({"role": "user", "content": {"type": "audio"}})
            st.rerun()

    # --- 「AI処理フェーズ」の定義 ---
    else:
        with st.chat_message("assistant"):
            if not gemini_api_key: 
                st.error("サイドバーでGemini APIキーを設定してください。")
            else:
                try:
                    with st.spinner("AIが予定を組み立てています..."):
                        genai.configure(api_key=gemini_api_key)
                        jst = pytz.timezone('Asia/Tokyo')
                        current_time_jst = datetime.now(jst).isoformat()
                        
                        # ★★★ ここが、ちゃろ様のアイデアの、核心部です ★★★
                        system_prompt = f"""
                        あなたは、ユーザーから渡されたテキスト、あるいは「音声」を直接解釈し、Googleカレンダーの予定を作成する、超高性能なAI秘書です。
                        - **もし入力が音声データの場合は、まず、その内容を、正確に、日本語で、文字に起こしてください。**
                        - その後、文字に起こした内容、あるいは、直接入力されたテキストから、「title」「start_time」「end_time」「location」「details」を抽出してください。
                        - 現在の日時は `{current_time_jst}` (JST)です。これを基準に日時を解釈してください。
                        - 日時は `YYYY-MM-DDTHH:MM:SS` 形式で出力してください。
                        - `end_time` が不明な場合は、`start_time` の1時間後を自動設定してください。
                        - 必ず以下のJSON形式のみで回答してください。他の言葉は一切含めないでください。
                        ```json
                        {{ "title": "（件名）", "start_time": "YYYY-MM-DDTHH:MM:SS", "end_time": "YYYY-MM-DDTHH:MM:SS", "location": "（場所）", "details": "（詳細）" }}
                        ```
                        """
                        model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                        
                        # テキストか音声かによって、モデルに渡す内容を変える
                        task_data = st.session_state.cal_task
                        response = model.generate_content(task_data) # Geminiが自動で形式を判断する

                        # 応答処理は共通
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
        
        # 完了：タスクを消去し、「待機フェーズ」に戻る
        st.session_state.cal_task = None
        st.session_state.cal_task_type = None
        time.sleep(1) 
        st.rerun()
