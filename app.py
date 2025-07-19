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
# 2. 認証処理の核心部（魂のパスポート作戦）
# ===============================================================
try:
    if "code" in st.query_params:
        time.sleep(0.2)
        saved_state = localS.getItem("google_auth_state")
        returned_state = st.query_params.get("state")
        if saved_state and saved_state == returned_state:
            localS.removeItem("google_auth_state")
            flow = Flow.from_client_config(
                client_config={
                    "web": { "client_id": st.secrets["GOOGLE_CLIENT_ID"], "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
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

            # ★★★ あなたのアイデアを、ここに、実装します ★★★
            st.session_state['auth_success'] = True # 認証成功のフラグを立てる
            st.query_params.clear()
            st.rerun() # UIを再描画するために、安全なリフレッシュを行う
except Exception as e:
    st.error("Google認証中にエラーが発生しました。")
    st.session_state['last_error'] = traceback.format_exc()

# ===============================================================
# 3. ログイン/ログアウト関数
# ===============================================================
def generate_login_url():
    flow = Flow.from_client_config(
        client_config={
            "web": { "client_id": st.secrets["GOOGLE_CLIENT_ID"], "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                     "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                     "redirect_uris": [st.secrets["REDIRECT_URI"]], }},
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri=st.secrets["REDIRECT_URI"],
    )
    authorization_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    localS.setItem("google_auth_state", state)
    return authorization_url

def google_logout():
    keys_to_clear = ["google_credentials", "google_auth_state", "google_user_info", "auth_success"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 4. サイドバー UI（常に表示される）
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    if "google_credentials" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        login_url = generate_login_url()
        st.link_button("🗝️ Googleアカウントでログイン", login_url, use_container_width=True)
    else:
        # このブロックが、認証直後にも、正しく、実行される！
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): google_logout()
    st.divider()

# ===============================================================
# 5. メインコンテンツの表示制御（賢者のUI制御）
# ===============================================================
# 認証成功直後か？
if st.session_state.get('auth_success', False):
    st.success("🎉 認証に成功しました！")
    if st.button("🚀 ポータルを開始する", use_container_width=True, type="primary"):
        st.session_state.pop('auth_success', None)
        st.rerun()
# まだログインしていないか？
elif "google_credentials" not in st.session_state:
    try:
        st.image("welcome.gif", use_container_width=True)
    except Exception as img_e:
        st.warning(f"ウェルカム画像の読み込みに失敗しました: {img_e}")
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
# ログイン済みか？
else:
    is_logged_in = True
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    with st.sidebar:
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, disabled=not is_logged_in)
        st.divider()
        if st.toggle("開発者モード", key="dev_mode", value=False):
            st.header("🗺️ 宝の地図")
            st.json({k: str(v) for k, v in st.session_state.items()})

    if tool_choice == "🚙 交通費自動計算":
        st.header("🚙 交通費自動計算ツール")
        st.success("ようこそ！ 認証システムは正常に稼働しています。")
        st.info("次のステップで、あなたのColabコードの魂を、ここに実装しましょう！")
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
    else:
        st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
