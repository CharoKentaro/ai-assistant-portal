# tools/calendar_tool.py

import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz
from st_audiorecorder import st_audiorecorder # ★ 1. 新しい録音ライブラリをインポート

# ===============================================================
# 補助関数（変更なし）
# ===============================================================

def transcribe_audio(audio_bytes, api_key):
    """Speech-to-Text APIを使用して音声データを文字に変換する関数"""
    if not audio_bytes or not api_key:
        return None
    try:
        client_options = ClientOptions(api_key=api_key)
        client = speech.SpeechClient(client_options=client_options)
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(language_code="ja-JP", model="latest_long")
        response = client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識中にエラーが発生しました。APIキーが正しいか、有効期限が切れていないかをご確認ください。詳細: {e}")
    return None

def create_google_calendar_url(details):
    """抽出された予定情報からGoogleカレンダー登録用のURLを生成する関数"""
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

# ===============================================================
# 専門家のメインの仕事 (司令塔 app.py から呼び出される)
# ===============================================================

def show_tool(gemini_api_key, speech_api_key):
    """カレンダー登録ツールのUIと機能をすべてここに集約"""
    st.header("📅 あなただけのAI秘書", divider='rainbow')

    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！私はあなただけのAI秘書です。ご予定を、下の３つの方法のいずれかでお伝えください。"}]
    
    for message in st.session_state.cal_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- ★ 2. ユーザー入力方法を3つに整理し、UIを再構築 ---
    prompt = None
    
    st.write("---")
    st.write("##### 方法１：マイクで直接話す")
    audio_bytes = st_audiorecorder(
        start_prompt="🎤 録音開始",
        stop_prompt="⏹️ 録音停止",
        pause_prompt="",
        key="cal_audio_recorder"
    )
    if audio_bytes:
        if not speech_api_key:
            st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
        else:
            with st.spinner("音声を文字に変換中..."):
                transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript:
                    st.success(f"音声認識結果: 「{transcript}」")
                    prompt = transcript
                else:
                    st.warning("音声の認識に失敗しました。")
    
    st.write("---")
    st.write("##### 方法２：音声ファイルをアップロードする")
    uploaded_file = st.file_uploader("音声ファイルを選択:", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
    if uploaded_file is not None:
        if not speech_api_key:
            st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
        else:
            with st.spinner("音声ファイルを文字に変換中..."):
                audio_bytes = uploaded_file.getvalue()
                transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript:
                    st.success(f"音声認識結果: 「{transcript}」")
                    prompt = transcript
                else:
                    st.warning("音声の認識に失敗しました。")
                    
    st.write("---")
    text_prompt = st.chat_input("方法３：キーボードで入力...", key="cal_text_input")
    if text_prompt:
        prompt = text_prompt
    # --- UIの再構築ここまで ---

    # --- ★ 3. どの方法で入力されても、同じAI処理が実行される ---
    if prompt:
        if not gemini_api_key:
            st.error("サイドバーでGemini APIキーを設定してください。")
            st.stop()

        st.session_state.cal_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            genai.configure(api_key=gemini_api_key)
            jst = pytz.timezone('Asia/Tokyo')
            current_time_jst = datetime.now(jst).isoformat()
            
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
                    json_text = response.text.strip().lstrip("```json").rstrip("```").strip()
                    schedule_details = json.loads(json_text)
                    calendar_url = create_google_calendar_url(schedule_details)
                    
                    display_start_time = "未設定"
                    if schedule_details.get('start_time'):
                        try:
                            display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y年%m月%d日 %H:%M')
                        except ValueError:
                             display_start_time = "AIが日付の解析に失敗しました"

                    ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。\n\n- **件名:** {schedule_details.get('title', '未設定')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', '未設定')}\n- **詳細:** {schedule_details.get('details', '未設定')}\n\n[📅 Googleカレンダーにこの予定を追加する]({calendar_url})"""
                    st.markdown(ai_response)
                    st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})
                    # 処理が終わったら再実行して、入力ウィジェットの状態をリセットする
                    st.rerun()

        except Exception as e:
            error_message = f"AIとの通信中にエラーが発生しました: {e}"
            st.error(error_message)
            st.session_state.cal_messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。"})
