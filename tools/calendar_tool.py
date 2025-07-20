import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz

# ===============================================================
# 補助関数（もともと成功コードにあったものを、そのまま移植）
# ===============================================================

def transcribe_audio(audio_bytes, api_key):
    """Speech-to-Text APIを使用して音声データを文字に変換する関数"""
    if not audio_bytes or not api_key:
        return None
    try:
        client_options = ClientOptions(api_key=api_key)
        client = speech.SpeechClient(client_options=client_options)
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(language_code="ja-JP")
        response = client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
    except Exception as e:
        # ユーザーに分かりやすいエラーメッセージを表示
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
        dates = "" # 日時が正しく取得できなかった場合は空にする

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
    st.header("📅 あなただけのAI秘書")
    st.info("テキストで直接入力するか、音声ファイルをアップロードして、カレンダーへの予定追加などをAIに伝えてください。")

    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！私はあなただけのAI秘書です。ご予定を何なりとお申し付けください。"}]

    for message in st.session_state.cal_messages:
        role = "model" if message["role"] == "assistant" else message["role"]
        with st.chat_message(role):
            st.markdown(message["content"])

    # --- ユーザーからの入力受付 ---
    prompt = None
    uploaded_file = st.file_uploader("音声ファイルをアップロード:", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
    if uploaded_file is not None:
        # 音声入力があった場合、Speech-to-Text APIキーの存在をチェック
        if not speech_api_key:
            st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
        else:
            with st.spinner("音声ファイルを文字に変換中..."):
                audio_bytes = uploaded_file.getvalue()
                transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript:
                    prompt = transcript
                else:
                    st.warning("音声の認識に失敗しました。")

    text_prompt = st.chat_input("または、キーボードで入力...", key="cal_text_input")
    if text_prompt:
        prompt = text_prompt

    # --- AIへのリクエスト処理 ---
    if prompt:
        # テキストまたは音声入力があった場合、Gemini APIキーの存在をチェック
        if not gemini_api_key:
            st.error("サイドバーでGemini APIキーを設定してください。")
            st.stop() # キーがなければ処理を中断

        st.session_state.cal_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            genai.configure(api_key=gemini_api_key)
            jst = pytz.timezone('Asia/Tokyo')
            current_time_jst = datetime.now(jst).isoformat()
            
            # 「成功コード」の魂である、洗練されたシステムプロンプト
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
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    schedule_details = json.loads(json_text)
                    calendar_url = create_google_calendar_url(schedule_details)
                    
                    display_start_time = "未設定"
                    if schedule_details.get('start_time'):
                        display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M')

                    ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。\n\n- **件名:** {schedule_details.get('title', '未設定')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', '未設定')}\n- **詳細:** {schedule_details.get('details', '未設定')}\n\n[📅 Googleカレンダーにこの予定を追加する]({calendar_url})"""
                    st.markdown(ai_response)
                    st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})

        except Exception as e:
            st.error(f"AIとの通信中にエラーが発生しました: {e}")
            st.session_state.cal_messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})
