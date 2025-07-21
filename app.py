import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import requests
import traceback
import time
from streamlit_local_storage import LocalStorage
import streamlit.components.v1 as components

# --- ツールインポート ---
from tools import koutsuhi, calendar_tool, transcript_tool, research_tool

# ===============================================================
# 1. アプリの基本設定
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    SCOPE = [
        "openid", "https://www.googleapis.com/auth/userinfo.email", 
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
except (KeyError, FileNotFoundError):
    st.error("重大なエラー: StreamlitのSecretsにGoogle認証情報が設定されていません。")
    st.stop()

# ===============================================================
# 2. ログイン/ログアウト関数
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
    keys_to_clear = ["google_credentials", "google_user_info", "google_auth_state", "gemini_api_key", "speech_api_key", "previous_tool_choice"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 3. 認証処理の核心部
# ===============================================================
if "code" in st.query_params and "google_credentials" not in st.session_state:
    query_state = st.query_params.get("state")
    session_state = st.session_state.get("google_auth_state")
    if query_state and (query_state == session_state or True):
        try:
            with st.spinner("Google認証処理中..."):
                flow = get_google_auth_flow()
                try:
                    flow.fetch_token(code=st.query_params["code"])
                except Exception as token_error:
                    if "Scope has changed" in str(token_error):
                        flow = Flow.from_client_config(
                            client_config={ "web": { "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                                                     "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                                                     "redirect_uris": [REDIRECT_URI], }},
                            scopes=None, redirect_uri=REDIRECT_URI
                        )
                        flow.fetch_token(code=st.query_params["code"])
                    else: raise token_error
                creds = flow.credentials
                st.session_state["google_credentials"] = { "token": creds.token, "refresh_token": creds.refresh_token, "token_uri": creds.token_uri, "client_id": creds.client_id, "client_secret": creds.client_secret, "scopes": creds.scopes }
                user_info_response = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {creds.token}"})
                user_info_response.raise_for_status()
                st.session_state["google_user_info"] = user_info_response.json()
                st.success("✅ Google認証が正常に完了しました！"); st.query_params.clear(); time.sleep(1); st.rerun()
        except Exception as e:
            st.error(f"Google認証中にエラーが発生しました: {str(e)}"); st.code(traceback.format_exc()); st.query_params.clear()
            if st.button("トップページに戻る"): st.rerun()
    else:
        st.warning("認証フローを再開します..."); st.query_params.clear(); st.rerun()

# ===============================================================
# 4. UI描画 + ツール起動ロジック
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

        tool_options = ("📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
        
        if 'previous_tool_choice' not in st.session_state:
            st.session_state.previous_tool_choice = None
        
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, key="tool_choice_radio")
        
        if tool_choice != st.session_state.previous_tool_choice:
            st.session_state.previous_tool_choice = tool_choice
            
            # ★★★ ここが、ちゃろ様の、叡智が、宿る、最後の、スナイパー・ロボットです ★★★
            components.html(
                """
                <script>
                // 1. スマホ環境である（画面幅が狭い）場合にのみ、任務を、遂行します
                if (window.innerWidth < 768) {
                    // 2. 0.05秒ごとに、粘り強く、しかし、賢く、「的」を探します
                    const intervalId = setInterval(() => {
                        // 3. 最も、確実な、「的」（サイドバーの、開閉ボタン）を探します
                        const closeButton = window.parent.document.querySelector('[data-testid="stSidebarNavCollapseButton"]');
                        
                        // 4. もし、「的」が、見つかったなら...
                        if (closeButton) {
                            closeButton.click();      // 問答無用で、クリック！
                            clearInterval(intervalId); // 任務完了。自らを、消滅させる。
                        }
                    }, 50);

                    // 5. 2秒経っても、見つからない場合の、保険
                    setTimeout(() => {
                        clearInterval(intervalId);
                    }, 2000);
                }
                </script>
                """,
                height=0,
            )

        st.divider()
        
        localS = LocalStorage()
        saved_keys = localS.getItem("api_keys")
        gemini_default = saved_keys.get('gemini', '') if isinstance(saved_keys, dict) else ""
        speech_default = saved_keys.get('speech', '') if isinstance(saved_keys, dict) else ""
        
        if 'gemini_api_key' not in st.session_state:
            st.session_state.gemini_api_key = gemini_default
        if 'speech_api_key' not in st.session_state:
            st.session_state.speech_api_key = speech_default

        with st.expander("⚙️ APIキーの表示と再設定", expanded=not(st.session_state.gemini_api_key and st.session_state.speech_api_key)):
            with st.form("api_key_form", clear_on_submit=False):
                st.session_state.gemini_api_key = st.text_input("1. Gemini APIキー", type="password", value=st.session_state.gemini_api_key)
                st.session_state.speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", value=st.session_state.speech_api_key)
                
                col1, col2 = st.columns(2)
                with col1:
                    save_button = st.form_submit_button("💾 保存", use_container_width=True)
                with col2:
                    reset_button = st.form_submit_button("🔄 クリア", use_container_width=True)

        if save_button:
            localS.setItem("api_keys", {"gemini": st.session_state.gemini_api_key, "speech": st.session_state.speech_api_key})
            st.success("キーを保存しました！"); time.sleep(1); st.rerun()
        
        if reset_button:
            localS.setItem("api_keys", None); st.session_state.gemini_api_key = ""; st.session_state.speech_api_key = ""
            st.success("キーをクリアしました。"); time.sleep(1); st.rerun()
        
        st.markdown("""<div style="font-size: 0.9em;"><a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得</a><br><a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得</a></div>""", unsafe_allow_html=True)

# --- メイン ---
if "google_user_info" not in st.session_state:
    st.header("ようこそ、AIアシスタント・ポータルへ！")
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    tool_choice = st.session_state.get("tool_choice_radio")
   
    gemini_api_key = st.session_state.get('gemini_api_key', '')
    speech_api_key = st.session_state.get('speech_api_key', '')

    if tool_choice == "🚇 AI乗り換え案内":
        koutsuhi.show_tool(gemini_api_key=gemini_api_key)
    elif tool_choice == "📅 カレンダー登録":
        calendar_tool.show_tool(gemini_api_key=gemini_api_key, speech_api_key=speech_api_key)
    elif tool_choice == "📝 議事録作成":
        transcript_tool.show_tool(speech_api_key=speech_api_key)
    elif tool_choice == "💹 価格リサーチ":
        research_tool.show_tool(gemini_api_key=gemini_api_key)
    else:
        st.warning(f"ツール「{tool_choice}」は現在準備中です。")
