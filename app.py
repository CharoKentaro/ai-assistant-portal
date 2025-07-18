import streamlit as st
import openai
import json
from datetime import datetime, timedelta
import urllib.parse

# --- アプリの基本設定 ---
st.set_page_config(
    page_title="AIアシスタント・ポータル",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AIアシスタント・ポータル")
st.caption("あなたの業務をAIがサポートします")

# --- サイドバー：APIキー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    openai_api_key = st.text_input("OpenAI APIキー", type="password")
    st.markdown("""
    <div style="font-size: 0.9em;">
    OpenAIのAPIキーをここに貼り付けてください。<br>
    <a href="https://platform.openai.com/account/api-keys" target="_blank">APIキーの取得はこちら</a>
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
    # 日時をGoogleカレンダーが要求する形式 (YYYYMMDDTHHMMSSZ) に変換
    try:
        start_time_dt = datetime.fromisoformat(details['start_time'])
        end_time_dt = datetime.fromisoformat(details['end_time'])
        
        # UTC形式の文字列に変換（ZはUTCを示す）
        start_time_str = start_time_dt.strftime('%Y%m%dT%H%M%SZ')
        end_time_str = end_time_dt.strftime('%Y%m%dT%H%M%SZ')

        dates = f"{start_time_str}/{end_time_str}"
    except (ValueError, KeyError):
        # 日時が正しく取得できなかった場合はdatesを空にする
        dates = ""

    # URLエンコード
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
# チャット履歴の初期化
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "こんにちは！どのようなご予定を登録しますか？"}
    ]

# 履歴の表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザーからの入力
if prompt := st.chat_input("予定を入力してください..."):
    # APIキーのチェック
    if not openai_api_key:
        st.error("サイドバーにOpenAI APIキーを入力してください。")
        st.stop()

    # ユーザーのメッセージを履歴に追加して表示
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AIへのリクエスト
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        
        system_prompt = f"""
        あなたは、自然言語からGoogleカレンダーの予定を作成するための情報を抽出する、非常に優秀なアシスタントです。
        ユーザーのテキストから「title (件名)」「start_time (開始日時)」「end_time (終了日時)」「location (場所)」「details (詳細説明)」を抽出してください。
        - 現在の日時は `{datetime.now().isoformat()}` です。これを基準に「明日」「来週」などを解釈してください。
        - 日時は必ず `YYYY-MM-DDTHH:MM:SS` というISO 8601形式で出力してください。
        - `end_time` が不明な場合は、`start_time` の1時間後を自動的に設定してください。
        - 抽出した情報は、必ず以下のJSON形式のみで回答してください。他の言葉は一切含めないでください。
        {{
          "title": "（ここに件名）",
          "start_time": "YYYY-MM-DDTHH:MM:SS",
          "end_time": "YYYY-MM-DDTHH:MM:SS",
          "location": "（ここに場所）",
          "details": "（ここに詳細）"
        }}
        """

        with st.chat_message("assistant"):
            with st.spinner("AIが予定を組み立てています..."):
                response = client.chat.completions.create(
                    model="gpt-4o",  # 最新の高性能モデルを利用
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                # AIからの応答（JSON）を解析
                schedule_details = json.loads(response.choices[0].message.content)
                
                # GoogleカレンダーのURLを生成
                calendar_url = create_google_calendar_url(schedule_details)
                
                # AIの応答メッセージを作成
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
