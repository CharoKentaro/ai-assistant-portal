# (変更点は1箇所のみですが、私たちの原則に従い、完全なコードを提供します)
import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz
import pandas as pd
# from streamlit_local_storage import LocalStorage

# --- 新しい仲間たちのインポート ---
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback

# ===============================================================
# 1. アプリの基本設定と、神聖なる金庫からの情報取得
# ===============================================================

st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

try:
    GOOGLE_CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
except (KeyError, FileNotFoundError):
    st.error("重大なエラー: StreamlitのSecretsにGoogle認証情報が設定されていません。")
    st.stop()

# ===============================================================
# 2. 『金庫番（トークンマネージャー）』と『セッション・ブリッジ』
# ===============================================================

def get_google_auth_flow():
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
    flow = get_google_auth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline", prompt="consent"
    )
    st.session_state["google_auth_state"] = state
    st.markdown(f'<meta http-equiv="refresh" content="0; url={authorization_url}">', unsafe_allow_html=True)
    st.rerun()

def google_logout():
    keys_to_clear = ["google_credentials", "google_auth_state", "google_user_info"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.success("ログアウトしました。")
    st.rerun()

try:
    if "code" in st.query_params and "state" in st.query_params:
        if "google_auth_state" in st.session_state and st.session_state["google_auth_state"] == st.query_params["state"]:
                flow = get_google_auth_flow()
                flow.fetch_token(code=st.query_params["code"])
                creds = flow.credentials
                st.session_state["google_credentials"] = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                }
                user_info_response = requests.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                if user_info_response.status_code == 200:
                    st.session_state["google_user_info"] = user_info_response.json()

                st.query_params.clear()
                st.rerun()
except Exception as e:
    st.error(f"Google認証中にエラーが発生しました: {e}")
    st.session_state['last_error'] = traceback.format_exc()
    st.rerun()

# ===============================================================
# 3. サイドバー UI
# ===============================================================

with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")

    if "google_credentials" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        if st.button("🗝️ Googleアカウントでログイン", use_container_width=True):
            google_login()
    else:
        user_info = st.session_state.get("google_user_info", {})
        st.success(f"✅ ログイン中")
        if 'name' in user_info:
            st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info:
            st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True):
            google_logout()

    st.divider()

    is_logged_in = "google_credentials" in st.session_state
    tool_options = ("📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内", "🚙 交通費自動計算")
    tool_choice = st.radio(
        "使いたいツールを選んでください:",
        tool_options,
        index=4 if is_logged_in else 0,
        disabled=not is_logged_in
    )

    st.divider()

    if st.toggle("開発者モード", key="dev_mode", value=False):
        st.header("🗺️ 宝の地図（開発者情報）")
        with st.expander("セッション情報 (st.session_state)", expanded=False):
            session_dict = {k: str(v) for k, v in st.session_state.items()}
            st.json(session_dict)
        with st.expander("直近のエラーログ", expanded=False):
            st.text(st.session_state.get('last_error', 'エラーは記録されていません。'))

    st.divider()

    st.markdown("""
    <div style="font-size: 0.9em; opacity: 0.5;">
    --- レガシーAPIキー設定 ---<br>
    <a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得</a><br>
    <a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得</a>
    </div>
    """, unsafe_allow_html=True)

# ===============================================================
# 4. メインコンテンツ
# ===============================================================

if "google_credentials" not in st.session_state:
    # ★★★ ここが、修正箇所です！ ★★★
    st.image("https://storage.googleapis.com/gemini-prod/images/41b18482-de0a-42b7-a868-23e3f3115456.gif", use_container_width=True)
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
    st.stop()

if tool_choice == "🚙 交通費自動計算":
    st.header("🚙 交通費自動計算ツール (PoC)")
    st.info("現在、認証システムの検証中です。認証が成功している場合、以下のメッセージが表示されます。")

    try:
        creds_dict = st.session_state["google_credentials"]
        credentials = Credentials(**creds_dict)
        gc = gspread.authorize(credentials)

        st.success("認証成功！ Googleスプレッドシートへのアクセス準備が整いました。")
        st.write("次のステップで、この認証情報を使って、あなたのColabコードのロジックをここに実装します。")

        with st.spinner("アクセス可能なスプレッドシートのリストを取得中..."):
            spreadsheet_list = gc.list_spreadsheet_files()
            st.write("アクセス可能なスプレッドシート (最新10件):")
            st.json([s['name'] for s in spreadsheet_list[:10]])

    except Exception as e:
        st.error(f"ツールの実行中にエラーが発生しました: {e}")
        st.session_state['last_error'] = traceback.format_exc()
        st.warning("エラーが発生しました。「開発者モード」の「宝の地図」で詳細を確認してください。")
        st.rerun()

elif tool_choice in ["📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内"]:
    st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
