import streamlit as st
import json
import urllib.parse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback

# ===============================================================
# 1. アプリの基本設定
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

# ===============================================================
# 2. ★★★ 作戦『賢者のクリック』の核心部 ★★★
# ===============================================================
try:
    # Googleからの帰還者がいるか、まず最初に確認
    if "code" in st.query_params:
        # 帰還者の身元確認（セッションに合言葉があるか？）
        if "google_auth_state" in st.session_state and st.session_state["google_auth_state"] == st.query_params["state"]:

            # --- 身分証明の儀式 ---
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                        "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [st.secrets["REDIRECT_URI"]],
                    }
                },
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
                redirect_uri=st.secrets["REDIRECT_URI"],
            )
            flow.fetch_token(code=st.query_params["code"])
            creds = flow.credentials

            # 「消えるインク」で、一旦、航海日誌に記録
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

            # ★★★ ここが新しい魔法です！ ★★★
            # 自動リフレッシュの代わりに、一度立ち止まり、ユーザーにクリックを促す
            st.session_state['auth_success'] = True
            # URLからコードを消すのは、次のステップで行う
            st.query_params.clear()


except Exception as e:
    st.error("Google認証中に、予期せぬエラーが発生しました。")
    st.session_state['last_error'] = traceback.format_exc()

# --- もし認証成功直後なら、賢者のクリックを促す画面を表示 ---
if st.session_state.get('auth_success', False):
    st.success("認証に成功しました！")
    if st.button("🎉 ポータルへ進む", use_container_width=True):
        # このクリックによって、インクは定着する！
        st.session_state.pop('auth_success', None) # このフラグはもう不要
        st.rerun() # ここで初めて、安全なリフレッシュを行う
    st.stop() # 他のUIは表示しない

# ===============================================================
# 3. ログイン/ログアウト関数の定義
# ===============================================================
def generate_login_url():
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": st.secrets["GOOGLE_CLIENT_ID"], "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [st.secrets["REDIRECT_URI"]],
            }
        },
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri=st.secrets["REDIRECT_URI"],
    )
    authorization_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    st.session_state["google_auth_state"] = state
    return authorization_url

def google_logout():
    keys_to_clear = ["google_credentials", "google_auth_state", "google_user_info"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 4. サイドバー UI
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    if "google_credentials" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        login_url = generate_login_url()
        st.link_button("🗝️ Googleアカウントでログイン", login_url, use_container_width=True)
    else:
        st.success(f"✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info:
            st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info:
            st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True):
            google_logout()
    st.divider()
    is_logged_in = "google_credentials" in st.session_state
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    tool_choice = st.radio("使いたいツールを選んでください:", tool_options, disabled=not is_logged_in)
    st.divider()
    if st.toggle("開発者モード", key="dev_mode", value=False):
        st.header("🗺️ 宝の地図")
        st.json({k: str(v) for k, v in st.session_state.items()})

# ===============================================================
# 5. メインコンテンツ
# ===============================================================
if "google_credentials" not in st.session_state:
    st.image("https://storage.googleapis.com/gemini-prod/images/41b18482-de0a-42b7-a868-23e3f3115456.gif", use_container_width=True)
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
    st.stop()

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
