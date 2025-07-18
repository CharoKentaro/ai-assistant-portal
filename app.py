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
    
    tool_choice = st.radio(
        "使いたいツールを選んでください:",
        ("📅 AIカレンダー秘書", "💹 価格リサーチ") # ★ツール名を変更
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

# --- バックエンド関数 (変更なし) ---
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    client_options = ClientOptions(api_key=api_key); client = speech.SpeechClient(client_options=client_options)
    audio = speech.RecognitionAudio(content=audio_bytes); config = speech.RecognitionConfig(language_code="ja-JP", audio_channel_count=1)
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
if tool_choice == "📅 AIカレンダー秘書":
    # (カレンダー秘書の機能は変更なし)
    st.header("📅 AIカレンダー秘書")
    st.info("テキストで直接入力するか、音声ファイルをアップロードして、カレンダーに追加したい予定をAIに伝えてください。")
    if "cal_messages" not in st.session_state: st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}]
    for message in st.session_state.cal_messages:
        role = "model" if message["role"] == "assistant" else message["role"]
        with st.chat_message(role): st.markdown(message["content"])
    prompt = None
    uploaded_file = st.file_uploader("音声ファイルをアップロード:", type=['wav', 'mp3', 'm4a', 'flac'], key="cal_uploader")
    if uploaded_file is not None:
        if not speech_api_key: st.error("サイドバーにSpeech-to-Text APIキーを入力してください。")
        else:
            with st.spinner("音声ファイルを文字に変換中..."):
                audio_bytes = uploaded_file.getvalue(); transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript: prompt = transcript
                else: st.warning("音声の認識に失敗しました。")
    text_prompt = st.chat_input("または、キーボードで入力...", key="cal_text_input")
    if text_prompt: prompt = text_prompt
    if prompt:
        if not gemini_api_key: st.error("サイドバーにGemini APIキーを入力してください。"); st.stop()
        st.session_state.cal_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        try:
            genai.configure(api_key=gemini_api_key); jst = pytz.timezone('Asia/Tokyo'); current_time_jst = datetime.now(jst).isoformat()
            system_prompt = f"""(省略)""" # カレンダー用のプロンプト(変更なし)
            model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
            with st.chat_message("assistant"):
                with st.spinner("AIが予定を組み立てています..."):
                    response = model.generate_content(prompt); json_text = response.text.strip().lstrip("```json").rstrip("```"); schedule_details = json.loads(json_text); calendar_url = create_google_calendar_url(schedule_details); display_start_time = "未設定"
                    if schedule_details.get('start_time'): display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M:%S')
                    ai_response = f"""(省略)""" # カレンダー用の応答(変更なし)
                    st.markdown(ai_response); st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})
        except Exception as e:
            st.error(f"エラーが発生しました: {e}"); st.session_state.cal_messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})

# ★★★ ここからが新しい「価格リサーチ」ツールの機能 ★★★
elif tool_choice == "💹 価格リサーチ":
    st.header("💹 万能！価格リサーチツール")
    st.info("調べたいもののキーワードを入力すると、AIが関連商品の価格情報をリサーチし、スプレッドシート用のファイル（CSV）を作成します。")

    # ★ユーザーがキーワードを入力する欄
    keyword = st.text_input("リサーチしたいキーワードを入力してください（例：20代向け メンズ香水, 北海道の人気お土産）")

    if st.button("このキーワードで価格情報をリサーチする"):
        if not gemini_api_key:
            st.error("サイドバーにGemini APIキーを入力してください。")
        elif not keyword:
            st.warning("キーワードを入力してください。")
        else:
            with st.spinner(f"AIが「{keyword}」の価格情報をリサーチしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    
                    # ★AIへの命令文に、ユーザーのキーワードを埋め込む
                    system_prompt = f"""
                    あなたは、ユーザーから指定されたキーワードに基づいて、関連商品のリストと、その平均的な価格を調査する、非常に優秀なリサーチアシスタントです。
                    ユーザーからのキーワードは「{keyword}」です。
                    このキーワードに関連する商品やサービスの情報を、20個、リストアップしてください。
                    情報は、必ず以下のJSON形式の配列のみで回答してください。他の言葉は一切含めないでください。
                    - 「name」には、商品名やサービス名を具体的に記入してください。
                    - 「price」には、日本円での平均的な販売価格を、必ず数値のみで記入してください。不明な場合は0と記入してください。
                    ```json
                    [
                      {{ "name": "（商品名1）", "price": (価格1) }},
                      {{ "name": "（商品名2）", "price": (価格2) }}
                    ]
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content(f"「{keyword}」に関連する商品・サービスの価格情報を20個教えてください。")
                    
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    item_list = json.loads(json_text)
                    
                    if not item_list:
                         st.warning("情報を取得できませんでした。キーワードを変えてお試しください。")
                    else:
                        # データをPandas DataFrameに変換
                        df = pd.DataFrame(item_list)
                        df.columns = ["項目名", "価格（円）"]
                        
                        # ★「価格（円）」列を数値に変換し、変換できないものはNaNにする
                        df['価格（円）'] = pd.to_numeric(df['価格（円）'], errors='coerce')
                        # NaN（価格不明）の行をリストの最後に持っていくために、大きな数値で埋める
                        df_sorted = df.sort_values(by="価格（円）", na_position='last')

                        st.success(f"「{keyword}」のリサーチが完了しました！")
                        
                        # ★並び替え済みのデータをCSVに変換
                        csv_data = df_sorted.to_csv(index=False, encoding='utf_8_sig').encode('utf_8_sig')
                        
                        st.download_button(
                            label=f"「{keyword}」の価格リストをダウンロード (.csv)",
                            data=csv_data,
                            file_name=f"{keyword}_research.csv",
                            mime="text/csv",
                        )
                        
                        # ★画面にも、並び替え済みのデータを表示
                        st.dataframe(df_sorted)

                except Exception as e:
                    st.error(f"リサーチ中にエラーが発生しました: {e}")
