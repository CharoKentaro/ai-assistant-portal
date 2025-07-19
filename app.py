import streamlit as st
import json
import urllib.parse
import pytz
from datetime import datetime
import pandas as pd
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
# ★★★ 作戦『絶対的観測』の核心部 ★★★
# 全てのUI描画の前に、まず最初にGoogleからの帰還を確認する！
# ===============================================================
try:
    # 帰還者のチェック (URLにcode= があるか？)
    if "code" in st.query_params:
        # 衛兵（セッション）が、出発時に持たせた合言葉を覚えているか？
        if "google_auth_state" in st.session_state and st.session_state["google_auth_state"] == st.query_params["state"]:
            
            # --- ここからが、身分証明の儀式 ---
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
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/userinfo.email",
                    "https://www.googleapis.com/auth/userinfo.profile",
                ],
                redirect_uri=st.secrets["REDIRECT_URI"],
            )
            
            # 帰還者が持つ通行許可証(code)を、正式な身分証明書(token)に交換
            flow.fetch_token(code=st.query_params["code"])
            creds = flow.credentials
            
            # 船内の名簿(session_state)に、身分情報を記録
            st.session_state["google_credentials"] = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
            }
            
            # 顔写真と名前も取得して、名簿に追加
            user_info_response = requests.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            if user_info_response.status_code == 200:
                st.session_state["google_user_info"] = user_info_response.json()
            
            # 無限ループを防ぐため、URLから通行許可証を消し去り、ページを再読み込み
            st.query_params.clear()
            st.rerun()

except Exception as e:
    st.error("Google認証中に、予期せぬエラーが発生しました。")
    st.session_state['last_error'] = traceback.format_exc()

# ===============================================================
# 2. ログイン/ログアウト関数の定義
# ===============================================================

def generate_login_url():
    """Googleログイン用の魔法のリンクを生成する関数"""
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
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/userinfo.email",
                    "https://www.googleapis.com/auth/userinfo.profile",
                ],
                redirect_uri=st.secrets["REDIRECT_URI"],
            )
    authorization_url, state = flow.authorization_url(
        access_type="offline", prompt="consent"
    )
    st.session_state["google_auth_state"] = state
    return authorization_url

def google_logout():
    """ログアウト処理関数"""
    keys_to_clear = ["google_credentials", "google_auth_state", "google_user_info"]
    for key in keys_to_clear:
        # pop(key, None) を使い、キーが存在しなくてもエラーにならないようにする
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 3. サイドバー UI
# ===============================================================

with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")

    # 名簿に身分情報があるか？
    if "google_credentials" not in st.session_state:
        # なければ、ログイン用の魔法のリンクを表示
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        login_url = generate_login_url()
        st.link_button("🗝️ Googleアカウントでログイン", login_url, use_container_width=True)
    else:
        # あれば、歓迎のメッセージを表示
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
    tool_choice = st.radio(
        "使いたいツールを選んでください:",
        tool_options,
        disabled=not is_logged_in
    )

    st.divider()

    if st.toggle("開発者モード", key="dev_mode", value=False):
        st.header("🗺️ 宝の地図（開発者情報）")
        with st.expander("現在のURLクエリパラメータ", expanded=False):
            st.json(st.query_params.to_dict())
        with st.expander("セッション情報 (st.session_state)", expanded=True):
            session_dict = {k: str(v) for k, v in st.session_state.items()}
            st.json(session_dict)
        with st.expander("直近のエラーログ", expanded=False):
            st.text(st.session_state.get('last_error', 'エラーは記録されていません。'))
    
    # (レガシーAPIキー部分は変更なし)

# ===============================================================
# 4. メインコンテンツ
# ===============================================================

if "google_credentials" not in st.session_state:
    st.image("https://storage.googleapis.com/gemini-prod/images/41b18482-de0a-42b7-a868-23e3f3115456.gif", use_container_width=True)
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
    st.stop()

# --- ここからが、ログイン後に表示される各ツール ---

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
        st.warning("エラーが発生しました。「開発者モード」の「宝の地図」で詳細を確認してください。")

else:
    st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
