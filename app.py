import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback
import time

# ===============================================================
# 1. アプリの基本設定と、神聖なる金庫からの情報取得
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
except (KeyError, FileNotFoundError):
    st.error("重大なエラー: StreamlitのSecretsにGoogle認証情報が設定されていません。")
    st.stop()

# ===============================================================
# 2. ログイン/ログアウト関数の定義（賢者の遺産バージョン）
# ===============================================================
def get_google_auth_flow():
    """Google認証のフローを生成する、ただ一つの、関数"""
    return Flow.from_client_config(
        client_config={ "web": { "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                                 "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                                 "redirect_uris": [REDIRECT_URI], }},
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )

def google_logout():
    """ログアウト処理関数"""
    keys_to_clear = ["google_credentials", "google_user_info", "google_auth_state"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 3. 認証処理の核心部（自然なコードフロー）
# ===============================================================
# --- Googleからの帰還者（URLにcodeがある者）がいるか、チェックする ---
if "code" in st.query_params and "state" in st.query_params:
    # 帰還者が、セッションに保存された合言葉を持っているか、チェックする
    # この時点で、まだログイン情報はセッションにないはず
    if "google_credentials" not in st.session_state:
        if st.session_state.get("google_auth_state") == st.query_params["state"]:
            try:
                flow = get_google_auth_flow()
                # 通行許可証(code)を、正式な身分証明書(token)に交換
                flow.fetch_token(code=st.query_params["code"])
                creds = flow.credentials

                # 航海日誌（session_state）に、身分情報を記録
                st.session_state["google_credentials"] = {
                    "token": creds.token, "refresh_token": creds.refresh_token, "token_uri": creds.token_uri,
                    "client_id": creds.client_id, "client_secret": creds.client_secret, "scopes": creds.scopes,
                }

                # ユーザー情報を取得して記録
                user_info_response = requests.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                if user_info_response.status_code == 200:
                    st.session_state["google_user_info"] = user_info_response.json()
                else:
                    st.warning("ユーザー情報の取得に失敗しました。")

                # URLを綺麗にして、ページをリフレッシュ！
                st.query_params.clear()
                st.rerun()

            except Exception as e:
                st.error("Google認証中に、予期せぬエラーが発生しました。")
                st.session_state['last_error'] = traceback.format_exc()
                st.code(st.session_state['last_error'])
        else:
            st.error("認証セッションが無効です。もう一度お試しください。")
            time.sleep(2)
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
        authorization_url, state = flow.authorization_url(prompt="consent", access_type="offline")
        # 合言葉を、セッションに、記録する
        st.session_state["google_auth_state"] = state
        st.link_button("🗝️ Googleアカウントでログイン", authorization_url, use_container_width=True)
    else:
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): google_logout()
    st.divider()

# --- メインコンテンツ ---
if "google_user_info" not in st.session_state:
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    with st.sidebar:
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, disabled=False)
        st.divider()
        if st.toggle("開発者モード", key="dev_mode", value=False):
            st.header("🗺️ 宝の地図")
            st.write("🪪 現在のセッション情報:", st.session_state)
            if "last_error" in st.session_state:
                with st.expander("直近のエラーログ", expanded=True):
                    st.code(st.session_state["last_error"])

    if tool_choice == "🚙 交通費自動計算":
        st.header("🚙 交通費自動計算ツール")
        st.success("ようこそ！ 認証システムは、ついに、正常に稼働しました。")
        try:
            creds = Credentials(**st.session_state["google_credentials"])
            gc = gspread.authorize(creds)
            with st.spinner("Googleスプレッドシートへの接続をテスト中..."):
                spreadsheet_list = gc.list_spreadsheet_files()
                st.write("アクセス可能なスプレッドシート (最新10件):")
                st.json([s['name'] for s in spreadsheet_list[:10]])
        except Exception as e:
            st.error(f"ツールの実行中にエラーが発生しました: {e}")
            st.code(traceback.format_exc())
    else:
        st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
