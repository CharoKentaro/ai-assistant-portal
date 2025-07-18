import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime
import urllib.parse

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


# --- GoogleカレンダーURL生成関数 ---
def create_google_calendar_url(details):
    try:
        start_time_dt = datetime.fromisoformat(details['start_time'])
        end_time_dt = datetime.fromisoformat(details['end_time'])
        
        start_time_str = start_time_dt.strftime('%Y%m%dT%H%M%SZ')
        end_time_str = end_time_dt.strftime('%Y%m%dT%H%M%SZ')

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

# --- チャット機能 ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}
    ]

for message in st.session_state.messages:
    # "assistant" roleを "model" にマッピング
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
        
        system_prompt = f"""
        あなたは、自然言語からGoogleカレンダーの予定を作成するための情報を抽出する、非常に優秀なアシスタントです。
        ユーザーのテキストから「title (件名)」「start_time (開始日時)」「end_time (終了日時)」「location (場所)」「details (詳細説明)」を抽出してください。
        - 現在の日時は `{datetime.now().isoformat()}` です。これを基準に「明日」「来週」などを解釈してください。
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
                
                # AIからの応答（JSON）を解析
                # レスポンスからJSON部分を抽出
                json_text = response.text.strip().lstrip("```json").rstrip("```")
                schedule_details = json.loads(json_text)
                
                calendar_url = create_google_calendar_url(schedule_details)
                
                ai_response = f"""以下の内容で承りました。よろしければリンクをクリックしてカレンダーに登録してください。

- **件名:** {schedule_details.get('title', '未設定')}
- **日時:** {schedule_details.get('start_time', '未設定').replace('T', ' ')}
- **場所:** {schedule_details.get('location', '未設定')}
- **詳細:** {schedule_details.get('details', '未設定')}

[📅 Googleカレンダーにこの予定を追加する]({calendar_url})
"""
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.session_state.messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました。({e})"})
