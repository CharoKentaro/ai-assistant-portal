import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import requests
import traceback
import time
from streamlit_local_storage import LocalStorage

# ★★★ 変更点①：専門家のインポート ★★★
# toolsフォルダから、専門家であるkoutsuhiと、新しいcalendar_toolモジュールをインポート
from tools import koutsuhi, calendar_tool

# ===============================================================
# 1. アプリの基本設定と、神聖なる金庫からの情報取得
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    SCOPE = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email", 
        "https://www.googleapis.com/auth/userinfo.profile",
        # gspreadを使う場合は必要だが、現状は不要なためコメントアウト。将来の拡張性のために残す。
        # "https://www.googleapis.com/auth/spreadsheets",
        # "https://www.googleapis.com/auth/drive.readonly"
    ]
except (KeyError, FileNotFoundError):
    st.error("重大なエラー: StreamlitのSecretsにGoogle認証情報が設定されていません。")
    st.stop()

# ===============================================================
# 2. ログイン/ログアウト関数
# (このセクションは元のコードから変更ありません)
# ===============================================================
def get_google_auth_flow():
    return Flow.from_client_config(
        client_config={ "web": { "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                                 "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                                 "redirect_uris": [REDIRECT_URI], }},
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )

def google_logout():
    keys_to_clear = ["google_credentials", "google_user_info", "google_auth_state"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    # ログアウト後にAPIキーもクリアした方が親切かもしれないが、利便性を考え一旦保持
    st.rerun()

# ===============================================================
# 3. 認証処理の核心部
# (このセクションは元のコードから変更ありません)
# ===============================================================
if "code" in st.query_params and "google_credentials" not in st.session_state:
    query_state = st.query_params.get("state")
    session_state = st.session_state.get("google_auth_state")
    
    if query_state and (query_state == session_state or True):
        try:
            with st.spinner("Google認証処理中..."):
                flow = get_google_auth_flow()
                flow.fetch_token(code=st.query_params["code"])
                
                creds = flow.credentials
                st.session_state["google_credentials"] = {
                    "token": creds.token, "refresh_token": creds.refresh_token, "token_uri": creds.token_uri,
                    "client_id": creds.client_id, "client_secret": creds.client_secret, "scopes": creds.scopes,
                }
                
                user_info_response = requests.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                user_info_response.raise_for_status()
                st.session_state["google_user_info"] = user_info_response.json()
                
                st.success("✅ Google認証が正常に完了しました！")
                st.query_params.clear()
                time.sleep(1)
                st.rerun()
            
        except Exception as e:
            st.error(f"Google認証中にエラーが発生しました: {str(e)}")
            st.code(traceback.format_exc())
            st.query_params.clear()
            if st.button("トップページに戻る"):
                st.rerun()
    else:
        st.warning("認証フローを再開します...")
        st.query_params.clear()
        st.rerun()

# ===============================================================
# 4. UI描画
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    
    if "google_user_info" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        flow = get_google_auth_flow()
        authorization_url, state = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes='true')
        st.session_state["google_auth_state"] = state
        st.link_button("🗝️ Googleアカウントでログイン", authorization_url, use_container_width=True)
    else:
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): google_logout()

    st.divider()
    
    # ログイン後にツール選択とAPIキー設定を表示
    if "google_user_info" in st.session_state:
        tool_options = ("📅 カレンダー登録", "🚇 AI乗り換え案内", "💹 価格リサーチ", "📝 議事録作成")
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, key="tool_choice_radio")
        
        st.divider()
        st.header("⚙️ APIキー設定")
        
        # ★★★ 変更点②：「成功コード」のAPIキー管理機能をここに復活 ★★★
        localS = LocalStorage()
        saved_keys = localS.getItem("api_keys")
        gemini_default = saved_keys.get('gemini', '') if isinstance(saved_keys, dict) else ""
        speech_default = saved_keys.get('speech', '') if isinstance(saved_keys, dict) else ""

        gemini_api_key = st.text_input("1. Gemini APIキー", type="password", value=gemini_default, help="Google AI Studioで取得したキー")
        speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", value=speech_default, help="Google Cloud Platformで取得したキー")

        if st.button("APIキーをこのブラウザに保存する"):
            localS.setItem("api_keys", {"gemini": gemini_api_key, "speech": speech_api_key})
            st.success("キーを保存しました！")
        
        st.markdown("""
        <div style="font-size: 0.9em;">
        <a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得</a><br>
        <a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得</a>
        </div>
        """, unsafe_allow_html=True)


# --- メインコンテンツ ---
if "google_user_info" not in st.session_state:
    st.header("ようこそ、AIアシスタント・ポータルへ！")
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    # st.session_stateからツール選択を取得
    tool_choice = st.session_state.get("tool_choice_radio")
    
    st.header(f"{tool_choice}")
    st.divider()

    # ★★★ 変更点③：ユーザーの選択に応じて、専門家の仕事を呼び出す ★★★
    if tool_choice == "🚇 AI乗り換え案内":
        # 「AI乗り換え案内」が選ばれたら、koutsuhiモジュールのshow_tool関数を実行
        # (注：koutsuhi.pyも今後APIキーを受け取るように修正が必要です)
        koutsuhi.show_tool()
    
    elif tool_choice == "📅 カレンダー登録":
        # 「カレンダー登録」が選ばれたら、calendar_toolモジュールのshow_tool関数を実行
        # その際、司令塔が管理しているAPIキーを引数として渡す
        calendar_tool.show_tool(gemini_api_key=gemini_api_key, speech_api_key=speech_api_key)
    
    else:
        # まだ作られていないツールが選ばれた場合のメッセージ
        st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
