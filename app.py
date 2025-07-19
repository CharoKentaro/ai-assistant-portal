import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback
from streamlit_local_storage import LocalStorage
import time

# ===============================================================
# 1. アプリの基本設定
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")
localS = LocalStorage()

# ===============================================================
# 2. 認証処理の核心部（あなたのチェックポイントを反映）
# ===============================================================
try:
    if "code" in st.query_params:
        time.sleep(0.3)
        saved_state = localS.getItem("google_auth_state")
        returned_state = st.query_params.get("state")

        if saved_state and saved_state == returned_state:
            localS.removeItem("google_auth_state")
            flow = Flow.from_client_config(
                client_config={ "web": { "client_id": st.secrets["GOOGLE_CLIENT_ID"], "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                                         "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                                         "redirect_uris": [st.secrets["REDIRECT_URI"]], }},
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
                redirect_uri=st.secrets["REDIRECT_URI"],
            )
            flow.fetch_token(code=st.query_params["code"])
            creds = flow.credentials

            st.session_state["google_credentials"] = {
                "token": creds.token, "refresh_token": creds.refresh_token, "token_uri": creds.token_uri,
                "client_id": creds.client_id, "client_secret": creds.client_secret, "scopes": creds.scopes,
            }
            user_info_response = requests.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            if user_info_response.status_code == 200:
                st.session_state["google_user_info"] = user_info_response.json()

            # ✅ チェックポイント2：rerun と clear の順序を修正
            st.rerun()
            st.query_params.clear()

except Exception as e:
    # ✅ チェックポイント5：詳細なエラーログを出力
    st.error("Google認証中に、予期せぬエラーが発生しました。")
    st.session_state['last_error'] = traceback.format_exc()
    st.code(st.session_state['last_error'])


# ===============================================================
# 3. ログイン/ログアウト関数
# ===============================================================
def generate_login_url():
    flow = Flow.from_client_config(
        client_config={ "web": { "client_id": st.secrets["GOOGLE_CLIENT_ID"], "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                                 "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                                 "redirect_uris": [st.secrets["REDIRECT_URI"]], }},
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri=st.secrets["REDIRECT_URI"],
    )
    authorization_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    localS.setItem("google_auth_state", state)
    return authorization_url

def google_logout():
    keys_to_clear = ["google_credentials", "google_auth_state", "google_user_info"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 4. UI描画
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    # ✅ チェックポイント5：より厳格なログイン判定
    if "google_user_info" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        login_url = generate_login_url()
        st.link_button("🗝️ Googleアカウントでログイン", login_url, use_container_width=True)
    else:
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): google_logout()
    st.divider()

if "google_user_info" not in st.session_state:
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    with st.sidebar:
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, disabled=False)
        st.divider()
        if st.toggle("開発者モード", key="dev_mode", value=True): # デフォルトでONにする
            st.header("🗺️ 宝の地図")
            # ✅ チェックポイント1：セッション情報を常に表示
            st.write("🪪 現在のセッション情報:", st.session_state)
            if "last_error" in st.session_state:
                with st.expander("直近のエラーログ", expanded=True):
                    st.code(st.session_state["last_error"])


    if tool_choice == "🚙 交通費自動計算":
        st.header("🚙 交通費自動計算ツール")
        st.success("ようこそ！ 認証システムは正常に稼働しています。")
        try:
            creds_dict = st.session_state["google_credentials"]
            credentials = Credentials(**creds_dict)
            gc = gspread.authorize(credentials)
            with st.spinner("Googleスプレッドシートへの接続をテスト中..."):
                spreadsheet_list = gc.list_spreadsheet_files()
                st.write("アクセス可能なスプレッドシート (最新10件):")
                st.json([s['name'] for s in spreadsheet_list[:10]])
        except Exception as e:
            st.error(f"ツールの実行中にエラーが発生しました: {e}")
            st.session_state['last_error'] = traceback.format_exc()
            st.code(st.session_state['last_error'])
    else:
        st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
