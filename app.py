import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback
from streamlit_local_storage import LocalStorage # 最後の希望

# ===============================================================
# 1. アプリの基本設定
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")
localS = LocalStorage() # 魂のパスポートを発行する機関

# ===============================================================
# 2. ★★★ 作戦『魂のパスポート』の核心部 ★★★
# ===============================================================
try:
    # Googleからの帰還者（URLにcodeがある者）がいるか？
    if "code" in st.query_params:
        # パスポート（localStorage）に、合言葉の記録はあるか？
        saved_state = localS.getItem("google_auth_state")
        returned_state = st.query_params.get("state")

        if saved_state and saved_state == returned_state:
            # 記録は一致した！ 身分証明の儀式を開始する！
            localS.removeItem("google_auth_state") # パスポートは一度使ったら無効化する

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

            # 航海日誌（session_state）に、今度こそ、消えないインクで記録する
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

            # URLを綺麗にして、ページをリフレッシュ！
            # このrerunによって、UI全体が再描画され、「ログイン中」が表示される
            st.query_params.clear()
            st.rerun()
        else:
            st.error("認証セッションが無効です。もう一度ログインしてください。")

except Exception as e:
    st.error("Google認証中に、予期せぬエラーが発生しました。")
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
    # 合言葉を、記憶ではなく、パスポート（localStorage）に記録する！
    localS.setItem("google_auth_state", state)
    return authorization_url

def google_logout():
    keys_to_clear = ["google_credentials", "google_auth_state", "google_user_info"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 4. サイドバーとメインコンテンツの描画
# ===============================================================
# このブロックは、常に、スクリプトが上から下へ実行される過程で、
# 認証処理が終わった「後」に、実行される。
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    if "google_credentials" not in st.session_state:
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

if "google_credentials" not in st.session_state:
    st.image("https://storage.googleapis.com/gemini-prod/images/41b18482-de0a-42b7-a868-23e3f3115456.gif", use_container_width=True)
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    is_logged_in = True
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    with st.sidebar:
        # ログイン後にツール選択ラジオボタンを表示
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
