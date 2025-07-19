import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz
import pandas as pd
from streamlit_local_storage import LocalStorage

# --- 新しい仲間たちのインポート ---
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback # 宝の地図のための秘密兵器

# ===============================================================
# 1. アプリの基本設定と、神聖なる金庫からの情報取得
# ===============================================================

st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

# --- 金庫（st.secrets）からGoogle認証情報を取得 ---
# このtry-exceptは、ローカル開発時にsecretsがない場合のエラーを防ぐためのものです
try:
    GOOGLE_CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    # 必要な権限（スコープ）のリスト。今回はスプレッドシートとユーザー情報を読み取る権限。
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
except (KeyError, FileNotFoundError):
    st.error("重大なエラー: StreamlitのSecretsにGoogle認証情報が設定されていません。")
    st.stop() # 認証情報がないと何もできないので、ここで処理を停止

# --- ローカルストレージの初期化 ---
localS = LocalStorage()

# ===============================================================
# 2. 『金庫番（トークンマネージャー）』と『セッション・ブリッジ』
# ===============================================================

def get_google_auth_flow():
    """Google認証のフローを生成する関数"""
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

def google_login():
    """GoogleログインURLを生成し、ユーザーをリダイレクトする"""
    flow = get_google_auth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline", prompt="consent"
    )
    # セッションブリッジ作戦：stateをsession_stateに保存
    st.session_state["google_auth_state"] = state
    # st.experimental_set_query_paramsは古いので、st.rerun()で対応する
    st.markdown(f'<meta http-equiv="refresh" content="0; url={authorization_url}">', unsafe_allow_html=True)


def google_logout():
    """ログアウト処理。セッション情報をクリアする"""
    st.session_state.pop("google_credentials", None)
    st.session_state.pop("google_auth_state", None)
    st.session_state.pop("google_user_info", None)
    st.success("ログアウトしました。")
    st.rerun() # ページを再読み込みして状態を反映

# --- 『セッション・ブリッジ』の核心部分 ---
# Google認証からのリダイレクトを処理する
if "code" in st.query_params and "state" in st.query_params:
    # ログイン時に保存したstateと、返ってきたstateが一致するか確認（CSRF対策）
    if "google_auth_state" in st.session_state and st.session_state["google_auth_state"] == st.query_params["state"]:
        try:
            flow = get_google_auth_flow()
            # 認可コードを使ってトークンを取得
            flow.fetch_token(code=st.query_params["code"])
            # 取得した認証情報（トークン）をセッションに保存
            creds = flow.credentials
            st.session_state["google_credentials"] = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
            }
            # ユーザー情報を取得して表示
            user_info_response = requests.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            if user_info_response.status_code == 200:
                st.session_state["google_user_info"] = user_info_response.json()

            # URLからクエリパラメータを削除してリロード（無限ループを防ぐ）
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            st.error(f"Google認証トークンの取得中にエラーが発生しました: {e}")
            # エラーの詳細を「宝の地図」に記録
            st.session_state['last_error'] = traceback.format_exc()
            st.stop()


# ===============================================================
# 3. サイドバー UI
# ===============================================================

with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")

    # --- Google認証状態によって表示を切り替える ---
    if "google_credentials" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        if st.button("🗝️ Googleアカウントでログイン", use_container_width=True):
            google_login()
    else:
        user_info = st.session_state.get("google_user_info", {})
        st.success(f"✅ ログイン中")
        st.markdown(f"**ユーザー:** {user_info.get('name', '取得中...')}")
        st.markdown(f"**メール:** {user_info.get('email', '取得中...')}")
        if st.button("🔑 ログアウト", use_container_width=True):
            google_logout()

    st.divider()

    # --- ツール選択 ---
    # ログインしていない場合はツールを選択できないようにする
    is_logged_in = "google_credentials" in st.session_state
    tool_options = ("📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内", "🚙 交通費自動計算")
    tool_choice = st.radio(
        "使いたいツールを選んでください:",
        tool_options,
        disabled=not is_logged_in # ログイン状態によって無効化
    )

    st.divider()

    # --- 【新・作戦4】『宝の地図』システム ---
    if st.toggle("開発者モード", key="dev_mode"):
        st.header("🗺️ 宝の地図（開発者情報）")
        with st.expander("セッション情報 (st.session_state)", expanded=False):
            st.json(st.session_state.to_dict())
        with st.expander("直近のエラーログ", expanded=False):
            st.text(st.session_state.get('last_error', 'エラーは記録されていません。'))


    st.header("⚙️ APIキー設定（レガシー）")
    st.caption("以下のキーは古いツール用です。新しいツールはGoogle認証を使用します。")
    saved_keys = localS.getItem("api_keys")
    gemini_default = saved_keys['gemini'] if isinstance(saved_keys, dict) and 'gemini' in saved_keys else ""
    speech_default = saved_keys['speech'] if isinstance(saved_keys, dict) and 'speech' in saved_keys else ""
    gemini_api_key = st.text_input("1. Gemini APIキー", type="password", value=gemini_default)
    speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", value=speech_default)
    if st.button("APIキーをこのブラウザに保存する"):
        keys_to_save = {"gemini": gemini_api_key, "speech": speech_api_key}
        localS.setItem("api_keys", keys_to_save)
        st.success("キーを保存しました！")
    st.divider()
    st.markdown("""
    <div style="font-size: 0.9em;">
    <a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得</a><br>
    <a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得</a>
    </div>
    """, unsafe_allow_html=True)


# ===============================================================
# 4. メインコンテンツ
# ===============================================================

# ログインしていない場合は、メッセージを表示して処理を中断
if "google_credentials" not in st.session_state:
    st.info("👆 サイドバーからGoogleアカウントでログインしてください。")
    st.stop()


# --- ここから各ツールの実装 ---
# （既存のツールのコードは、現時点では変更しません）

if tool_choice == "🚙 交通費自動計算":
    st.header("🚙 交通費自動計算ツール (PoC)")
    st.info("現在、認証システムの検証中です。認証が成功している場合、以下のメッセージが表示されます。")

    try:
        # 『金庫番』が、セッションに保存しておいた鍵（クレデンシャル）を取り出す
        creds_dict = st.session_state["google_credentials"]
        credentials = Credentials(**creds_dict)

        # 鍵を使って、Googleスプレッドシートのクライアントを初期化する
        gc = gspread.authorize(credentials)

        st.success("認証成功！ Googleスプレッドシートへのアクセス準備が整いました。")
        st.write("次のステップで、この認証情報を使って、あなたのColabコードのロジックをここに実装します。")
        
        # 検証のため、アクセス可能なスプレッドシートの一覧を取得してみる
        with st.spinner("アクセス可能なスプレッドシートのリストを取得中..."):
            spreadsheet_list = gc.list_spreadsheet_files()
            st.write("アクセス可能なスプレッドシート:")
            st.json([s['name'] for s in spreadsheet_list[:10]]) # 最初の10件を表示

    except Exception as e:
        st.error(f"ツールの実行中にエラーが発生しました: {e}")
        st.session_state['last_error'] = traceback.format_exc()
        st.warning("エラーが発生しました。「開発者モード」の「宝の地図」で詳細を確認してください。")


# --- (これ以降の、既存ツールのifブロックは、省略せずにそのままここにペーストしてください) ---

elif tool_choice == "📅 カレンダー登録":
    # (既存の「カレンダー登録」のコードをここにそのまま記述)
    st.header("📅 あなただけのAI秘書")
    st.info("テキストで直接入力するか、音声ファイルをアップロードして、カレンダーへの予定追加などをAIに伝えてください。")
    # ... (以下、元のコードをそのまま続ける)
    if "cal_messages" not in st.session_state: st.session_state.cal_messages = [{"role": "assistant", "content": "こんにちは！私はあなただけのAI秘書です。サイドバーでAPIキーを登録して、自由に使ってくださいませ。まずはカレンダーにご予定をどうぞ！"}]
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
            def create_google_calendar_url(details):
                try:
                    jst = pytz.timezone('Asia/Tokyo'); start_time_naive = datetime.fromisoformat(details['start_time']); end_time_naive = datetime.fromisoformat(details['end_time']); start_time_jst = jst.localize(start_time_naive); end_time_jst = jst.localize(end_time_naive); start_time_utc = start_time_jst.astimezone(pytz.utc); end_time_utc = end_time_jst.astimezone(pytz.utc); start_time_str = start_time_utc.strftime('%Y%m%dT%H%M%SZ'); end_time_str = end_time_utc.strftime('%Y%m%dT%H%M%SZ'); dates = f"{start_time_str}/{end_time_str}"
                except (ValueError, KeyError): dates = ""
                base_url = "https://www.google.com/calendar/render?action=TEMPLATE"; params = { "text": details.get('title', ''), "dates": dates, "location": details.get('location', ''), "details": details.get('details', '') }; encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote); return f"{base_url}&{encoded_params}"
            with st.chat_message("assistant"):
                with st.spinner("AIが予定を組み立てています..."):
                    response = model.generate_content(prompt); json_text = response.text.strip().lstrip("```json").rstrip("```"); schedule_details = json.loads(json_text); calendar_url = create_google_calendar_url(schedule_details); display_start_time = "未設定"
                    if schedule_details.get('start_time'): display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M:%S')
                    ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。\n\n- **件名:** {schedule_details.get('title', '未設定')}\n- **日時:** {display_start_time}\n- **場所:** {schedule_details.get('location', '未設定')}\n- **詳細:** {schedule_details.get('details', '未設定')}\n\n[📅 Googleカレンダーにこの予定を追加する]({calendar_url})"""
                    st.markdown(ai_response); st.session_state.cal_messages.append({"role": "assistant", "content": ai_response})
        except Exception as e:
            st.error(f"エラーが発生しました: {e}"); st.session_state.cal_messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})

elif tool_choice == "💹 価格リサーチ":
    # (既存の「価格リサーチ」のコードをここにそのまま記述)
    st.header("💹 万能！価格リサーチツール")
    st.info("調べたいもののキーワードを入力すると、AIが関連商品の価格情報をリサーチし、スプレッドシート用のファイル（CSV）を作成します。")
    # ... (以下、元のコードをそのまま続ける)
    keyword = st.text_input("リサーチしたいキーワードを入力してください（例：20代向け メンズ香水, 北海道の人気お土産）")
    if st.button("このキーワードで価格情報をリサーチする"):
        if not gemini_api_key: st.error("サイドバーにGemini APIキーを入力してください。")
        elif not keyword: st.warning("キーワードを入力してください。")
        else:
            with st.spinner(f"AIが「{keyword}」の価格情報をリサーチしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
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
                    json_text = response.text.strip().lstrip("```json").rstrip("```"); item_list = json.loads(json_text)
                    if not item_list: st.warning("情報を取得できませんでした。キーワードを変えてお試しください。")
                    else:
                        df = pd.DataFrame(item_list); df.columns = ["項目名", "価格（円）"]; df['価格（円）'] = pd.to_numeric(df['価格（円）'], errors='coerce'); df_sorted = df.sort_values(by="価格（円）", na_position='last')
                        st.success(f"「{keyword}」のリサーチが完了しました！")
                        csv_data = df_sorted.to_csv(index=False, encoding='utf_8_sig').encode('utf_8_sig')
                        st.download_button(label=f"「{keyword}」の価格リストをダウンロード (.csv)", data=csv_data, file_name=f"{keyword}_research.csv", mime="text/csv")
                        st.dataframe(df_sorted)
                except Exception as e:
                    st.error(f"リサーチ中にエラーが発生しました: {e}")

elif tool_choice == "📝 議事録作成":
    # (既存の「議事録作成」のコードをここにそのまま記述)
    st.header("📝 音声ファイルから議事録を作成")
    st.info("会議などを録音した音声ファイルをアップロードすると、AIが文字起こしを行い、テキストファイルとしてダウンロードできます。")
    # ... (以下、元のコードをそのまま続ける)
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
    if "transcript_text" not in st.session_state: st.session_state.transcript_text = None
    議事録_file = st.file_uploader("議事録を作成したい音声ファイルをアップロードしてください:", type=['wav', 'mp3', 'm4a', 'flac'], key="transcript_uploader")
    if st.button("この音声ファイルから議事録を作成する"):
        if not speech_api_key: st.error("サイドバーにSpeech-to-Text APIキーを入力してください。")
        elif 議事録_file is None: st.warning("音声ファイルをアップロードしてください。")
        else:
            with st.spinner("音声ファイルを文字に変換しています。長い音声の場合、数分かかることがあります..."):
                audio_bytes = 議事録_file.getvalue(); transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript: st.session_state.transcript_text = transcript
                else: st.warning("音声の認識に失敗しました。ファイルが空か、形式が正しくない可能性があります。")
    if st.session_state.transcript_text:
        st.success("文字起こしが完了しました！")
        st.text_area("文字起こし結果", st.session_state.transcript_text, height=300)
        st.download_button(label="議事録をテキストファイルでダウンロード (.txt)", data=st.session_state.transcript_text.encode('utf_8'), file_name="transcript.txt", mime="text/plain")

elif tool_choice == "🚇 AI乗り換え案内":
    # (既存の「AI乗り換え案内」のコードをここにそのまま記述)
    st.header("🚇 AI乗り換え案内シミュレーター")
    st.info("出発地と目的地を入力すると、AIが標準的な所要時間や料金に基づいた最適なルートを3つ提案します。")
    # ... (以下、元のコードをそのまま続ける)
    st.warning("※これはリアルタイムの運行情報を反映したものではありません。あくまで目安としてご利用ください。")
    col1, col2 = st.columns(2)
    with col1:
        start_station = st.text_input("出発地を入力してください", "大阪")
    with col2:
        end_station = st.text_input("目的地を入力してください", "小阪")
    if st.button(f"「{start_station}」から「{end_station}」へのルートを検索"):
        if not gemini_api_key:
            st.error("サイドバーにGemini APIキーを入力してください。")
        else:
            with st.spinner(f"AIが最適なルートをシミュレーションしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    system_prompt = f"""
                    あなたは、日本の公共交通機関の膨大なデータベースを内蔵した、世界最高の「乗り換え案内エンジン」です。
                    ユーザーから指定された「出発地」と「目的地」に基づき、標準的な所要時間、料金、乗り換え情報を基に、最適な移動ルートをシミュレートするのがあなたの役割です。
                    
                    特に、以下の条件を厳格に守って、シミュレーション結果をJSON形式で出力してください。
                    
                    1.  **3つのルート提案:** 必ず、「早さ・安さ・楽さ」のバランスが良い、優れたルートを「3つ」提案してください。
                    2.  **厳格なJSONフォーマット:** 出力は、必ず、以下のJSON形式の配列のみで回答してください。他の言葉、説明、言い訳は、一切含めないでください。
                    3.  **経路の詳細 (steps):**
                        *   `transport_type`: "電車", "徒歩", "バス" などを明確に記述してください。
                        *   `line_name`: 電車の場合、「JR大阪環状線」や「近鉄奈良線」のように、路線名を正確に記述してください。
                        *   `station_from`: 乗車駅を記述してください。
                        *   `station_to`: 降車駅を記述してください。
                        *   `details`: 「〇〇方面行き」や「〇番線ホーム」など、補足情報があれば記述してください。徒歩の場合は、「〇〇駅まで歩く」のように記述してください。
                    4.  **サマリー情報:**
                        *   `total_time`: ルート全体の合計所要時間（分）を、数値のみで記述してください。
                        *   `total_fare`: ルート全体の合計料金（円）を、数値のみで記述してください。
                        *   `transfers`: 乗り換え回数を、数値のみで記述してください。
                    
                    ```json
                    [
                      {{
                        "route_name": "ルート1：最速",
                        "summary": {{ "total_time": 30, "total_fare": 450, "transfers": 1 }},
                        "steps": [
                          {{ "transport_type": "電車", "line_name": "JR大阪環状線", "station_from": "大阪", "station_to": "鶴橋", "details": "内回り" }},
                          {{ "transport_type": "徒歩", "details": "近鉄線へ乗り換え" }},
                          {{ "transport_type": "電車", "line_name": "近鉄奈良線", "station_from": "鶴橋", "station_to": "河内小阪", "details": "普通・奈良行き" }}
                        ]
                      }},
                      {{
                        "route_name": "ルート2：乗り換え楽",
                        "summary": {{ "total_time": 35, "total_fare": 480, "transfers": 0 }},
                        "steps": [
                          {{ "transport_type": "バス", "line_name": "市営バス12系統", "station_from": "大阪駅前", "station_to": "小阪駅前", "details": "" }}
                        ]
                      }},
                      {{
                        "route_name": "ルート3：最安",
                        "summary": {{ "total_time": 40, "total_fare": 400, "transfers": 2 }},
                        "steps": [
                        ]
                      }}
                    ]
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content(f"出発地：{start_station}, 目的地：{end_station}")
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    routes = json.loads(json_text)
                    st.success(f"AIによるルートシミュレーションが完了しました！")
                    for i, route in enumerate(routes):
                        with st.expander(f"**{route.get('route_name', 'ルート')}** - 約{route.get('summary', {}).get('total_time', '?')}分 / {route.get('summary', {}).get('total_fare', '?')}円 / 乗り換え{route.get('summary', {}).get('transfers', '?')}回", expanded=(i==0)):
                            last_station = end_station
                            if route.get('steps'):
                                for step in route['steps']:
                                    if step.get('transport_type') == "電車":
                                        st.markdown(f"**<font color='blue'>{step.get('station_from', '?')}</font>**", unsafe_allow_html=True)
                                        st.markdown(f"｜ 🚃 {step.get('line_name', '不明な路線')} ({step.get('details', '')})")
                                    elif step.get('transport_type') == "徒歩":
                                        st.markdown(f"**<font color='green'>👟 {step.get('details', '徒歩')}</font>**", unsafe_allow_html=True)
                                    elif step.get('transport_type') == "バス":
                                        st.markdown(f"**<font color='purple'>{step.get('station_from', '?')}</font>**", unsafe_allow_html=True)
                                        st.markdown(f"｜ 🚌 {step.get('line_name', '不明なバス')} ({step.get('details', '')})")
                            st.markdown(f"**<font color='red'>{last_station}</font>**", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"シミュレーション中にエラーが発生しました: {e}")
