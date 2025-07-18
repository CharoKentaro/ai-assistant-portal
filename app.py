import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime
import urllib.parse
import pytz # ★日本のタイムゾーンを扱うための部品を追加

# --- アプリの基本設定 ---
st.set_page_config(
    page_title="AIアシスタント・ポータル",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AIアシスタント・ポータル")
st.caption("あなたの業務をAIがサポートします (Powered by Google Gemini)")

# --- サイドバー：APIキー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    google_api_key = st.text_input("Google AI APIキー", type="password")
    st.markdown("""
    <div style="font-size: 0.9em;">
    Google AI StudioのAPIキーをここに貼り付けてください。<br>
    <a href="https://aistudio.google.com/app/apikey" target="_blank">APIキーの取得はこちら</a>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div style="font-size: 0.8em;">
    <strong>このアプリについて</strong><br>
    このアプリは、あなたの業務効率化を目的としています。入力されたAPIキーや会話内容は、サーバーに一切保存されません。
    </div>
    """, unsafe_allow_html=True)


# --- GoogleカレンダーURL生成関数 (タイムゾーン対応版) ---
def create_google_calendar_url(details):
    try:
        # ★日本のタイムゾーンを定義
        jst = pytz.timezone('Asia/Tokyo')

        # まずはタイムゾーン情報のない「naive」なdatetimeオブジェクトとして解釈
        start_time_naive = datetime.fromisoformat(details['start_time'])
        end_time_naive = datetime.fromisoformat(details['end_time'])
        
        # ★解釈した時刻を「日本時間」としてタイムゾーン情報を付与 (localize)
        start_time_jst = jst.localize(start_time_naive)
        end_time_jst = jst.localize(end_time_naive)
        
        # GoogleカレンダーURLはUTCで渡すのが最も確実なため、UTCに変換
        start_time_utc = start_time_jst.astimezone(pytz.utc)
        end_time_utc = end_time_jst.astimezone(pytz.utc)

        # Googleカレンダーが要求するUTC形式 (YYYYMMDDTHHMMSSZ) の文字列に変換
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

# --- メイン画面 ---
st.header("📅 AIカレンダー秘書")
st.info("「来週火曜の15時からAさんと会議」「明日の朝9時に企画書の作成」のように話しかけてみてください。")

# --- チャット機能 (変更なし) ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}
    ]

for message in st.session_state.messages:
    role = "model" if message["role"] == "assistant" else message["role"]
    with st.chat_message(role):
        st.markdown(message["content"])

if prompt := st.chat_input("予定を入力してください..."):
    if not google_api_key:
        st.error("サイドバーにGoogle AI APIキーを入力してください。")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        genai.configure(api_key=google_api_key)
        
        # ★AIへの指示にも、日本の現在時刻をタイムゾーン付きで教える
        jst = pytz.timezone('Asia/Tokyo')
        current_time_jst = datetime.now(jst).isoformat()
        
        system_prompt = f"""
        あなたは、自然言語からGoogleカレンダーの予定を作成するための情報を抽出する、非常に優秀なアシスタントです。
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
                
                # ★ユーザーへの表示も、タイムゾーンを考慮した日時を表示
                display_start_time = "未設定"
                if schedule_details.get('start_time'):
                    display_start_time = datetime.fromisoformat(schedule_details['start_time']).strftime('%Y-%m-%d %H:%M:%S')

                ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。

- **件名:** {schedule_details.get('title', '未設定')}
- **日時:** {display_start_time}
- **場所:** {schedule_details.get('location', '未設定')}
- **詳細:** {schedule_details.get('details', '未設定')}

[📅 Googleカレンダーにこの予定を追加する]({calendar_url})
"""
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.session_state.messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})
