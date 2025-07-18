import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz
import pandas as pd

# --- アプリの基本設定 ---
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

# --- サイドバー ---
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    
    # ★ここからツール選択機能を追加
    tool_choice = st.radio(
        "使いたいツールを選んでください:",
        ("📅 AIカレンダー秘書", "💄 人気コスメリサーチ")
    )
    st.divider()
    
    st.header("⚙️ 設定")
    gemini_api_key = st.text_input("1. Gemini APIキー", type="password", help="Google AI Studioで取得したキー")
    speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", help="Google Cloud Platformで取得したキー")
    st.divider()
    st.markdown("""
    <div style="font-size: 0.9em;">
    <a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得</a><br>
    <a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得</a>
    </div>
    """, unsafe_allow_html=True)

# --- バックエンド関数 (Speech-to-Text, Calendar URL) ---
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    client_options = ClientOptions(api_key=api_key)
    client = speech.SpeechClient(client_options=client_options)
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(language_code="ja-JP", audio_channel_count=1)
    try:
        response = client.recognize(config=config, audio=audio)
        if response.results: return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識エラー: {e}")
    return None

def create_google_calendar_url(details):
    try:
        jst = pytz.timezone('Asia/Tokyo'); start_time_naive = datetime.fromisoformat(details['start_time']); end_time_naive = datetime.fromisoformat(details['end_time']); start_time_jst = jst.localize(start_time_naive); end_time_jst = jst.localize(end_time_naive); start_time_utc = start_time_jst.astimezone(pytz.utc); end_time_utc = end_time_jst.astimezone(pytz.utc); start_time_str = start_time_utc.strftime('%Y%m%dT%H%M%SZ'); end_time_str = end_time_utc.strftime('%Y%m%dT%H%M%SZ'); dates = f"{start_time_str}/{end_time_str}"
    except (ValueError, KeyError): dates = ""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"; params = { "text": details.get('title', ''), "dates": dates, "location": details.get('location', ''), "details": details.get('details', '') }; encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote); return f"{base_url}&{encoded_params}"

# --- メイン画面の描画 ---
# ★選択されたツールに応じて、表示する内容を切り替える
if tool_choice == "📅 AIカレンダー秘書":
    st.header("📅 AIカレンダー秘書")
    st.info("テキストで直接入力するか、音声ファイルをアップロードして、カレンダーに追加したい予定をAIに伝えてください。")

    # --- セッションステートの初期化 (ツールごと) ---
    if "cal_messages" not in st.session_state:
        st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}]

    # チャット履歴の表示
    for message in st.session_state.cal_messages:
        role = "model" if message["role"] == "assistant" else message["role"]
        with st.chat_message(role):
            st.markdown(message["content"])

    # 入力部分
    prompt = None
    uploaded_file = st.file_uploader("音声ファイルをアップロード:", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
    if uploaded_file is not None:
        if not speech_api_key: st.error("サイドバーにSpeech-to-Text APIキーを入力してください。")
        else:
            with st.spinner("音声ファイルを文字に変換中..."):
                audio_bytes = uploaded_file.getvalue()
                transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript: prompt = transcript
                else: st.warning("音声の認識に失敗しました。")
    
    text_prompt = st.chat_input("または、キーボードで入力...", key="cal_text_input")
    if text_prompt: prompt = text_prompt

    # チャット処理
    if prompt:
        if not gemini_api_key: st.error("サイドバーにGemini APIキーを入力してください。"); st.stop()
        st.session_state.cal_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        try:
            genai.configure(api_key=gemini_api_key); jst = pytz.timezone('Asia/Tokyo'); current_time_jst = datetime.now(jst).isoformat()
            system_prompt = f"""
            あなたは、ユーザーから渡されたテキストを解釈し、Googleカレンダーの予定を作成する情報を抽出する、非常に優秀なアシスタントです。
            ユーザーのテキストから「title (件名)」「start_time (開始日時)」「end_time (終了日時)」「location (場所)」「details (詳細説明)」を抽出してください。
            - 現在の日時は `{current_time_jst}` です。
            - 日時は必ず `YYYY-MM-DDTHH:MM:SS` というISO 8601形式で出力してください。
            - `end_time` が不明な場合は、`start_time` の1時間後を自動的に設定してください。
            - 抽出した情報は、必ず以下のJSON形式のみで回答してください。
            ```json
            {{ "title": "...", "start_time": "...", "end_time": "...", "location": "...", "details": "..." }}
            ```
            """
            model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
            with st.chat_message("assistant"):
                with st.spinner("AIが予定を組み立てています..."):
                    response = model.generate_content(prompt); json_text = response.text.strip().lstrip("```json").rstrip("```"); schedule_details = json.loads(json_text); calendar_url = create_google_calendar_url(schedule_details); display_start_time = "未設定"
                    if schedule_details.get('start_time'): display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M:%S')
                    ai_response = f"""以下の内容で承りました。\n\n- **件名:** {schedule_details.get('title', '未設定')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', '未設定')}\n- **詳細:** {schedule_details.get('details', '未設定')}\n\n[📅 Googleカレンダーにこの予定を追加する]({calendar_url})"""
                    st.markdown(ai_response); st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})
        except Exception as e:
            st.error(f"エラーが発生しました: {e}"); st.session_state.cal_messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})


elif tool_choice == "💄 人気コスメリサーチ":
    st.header("💄 人気コスメリサーチ")
    st.info("ボタンを押すと、AIが最新の人気のコスメ情報をリサーチし、スプレッドシート用のファイル（CSV）を作成します。")
    
    if st.button("人気のコスメ情報をリサーチする"):
        if not gemini_api_key:
            st.error("サイドバーにGemini APIキーを入力してください。")
        else:
            with st.spinner("AIが人気のコスメ情報をリサーチしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    system_prompt = """
                    あなたは、日本の化粧品市場に非常に詳しい、優秀なリサーチアシスタントです。
                    現在、日本で人気のあるコスメ（化粧品）の情報を、20個、リストアップしてください。
                    情報は、必ず以下のJSON形式の配列のみで回答してください。他の言葉は一切含めないでください。
                    - 「name」には、ブランド名と商品名を両方含めてください。
                    - 「price」には、日本円での平均的な販売価格を、数値のみで記入してください。
                    ```json
                    [
                      { "name": "（ブランド名） - （商品名）", "price": (価格の数値) },
                      { "name": "（ブランド名） - （商品名）", "price": (価格の数値) }
                    ]
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content("人気のコスメ情報を20個教えてください。")
                    
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    cosme_list = json.loads(json_text)
                    
                    # データをPandas DataFrameに変換
                    df = pd.DataFrame(cosme_list)
                    # 列名を日本語に
                    df.columns = ["商品名", "価格（円）"]
                    
                    st.success("リサーチが完了しました！以下のボタンからファイルをダウンロードできます。")
                    
                    # CSVに変換（UTF-8 with BOMでExcelでの文字化けを防ぐ）
                    csv_data = df.to_csv(index=False, encoding='utf_8_sig').encode('utf_8_sig')
                    
                    st.download_button(
                        label="人気のコスメリストをダウンロード (.csv)",
                        data=csv_data,
                        file_name="popular_cosmetics.csv",
                        mime="text/csv",
                    )
                    
                    st.dataframe(df) # 結果を画面にも表示

                except Exception as e:
                    st.error(f"リサーチ中にエラーが発生しました: {e}")
