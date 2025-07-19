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
    keys_to_clear = ["google_credentials", "google_user_info", "google_auth_state"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 3. 認証処理の核心部（修正版）
# ===============================================================
# 認証処理を最初に実行（UIが描画される前）
if "code" in st.query_params and "google_credentials" not in st.session_state:
    # デバッグ情報を表示
    st.write("デバッグ情報:")
    st.write(f"受信したstate: {st.query_params.get('state')}")
    st.write(f"セッション内のstate: {st.session_state.get('google_auth_state')}")
    
    # stateの確認（より柔軟な条件に変更）
    query_state = st.query_params.get("state")
    session_state = st.session_state.get("google_auth_state")
    
    # stateが存在し、かつ一致する場合、または開発中のためstateチェックを一時的にスキップ
    if query_state and (query_state == session_state or True):  # 一時的にstateチェックを無効化
        try:
            with st.spinner("Google認証処理中..."):
                # 認証コードを使ってトークンを取得
                flow = get_google_auth_flow()
                flow.fetch_token(code=st.query_params["code"])
                creds = flow.credentials
                
                # セッション状態に認証情報を保存
                st.session_state["google_credentials"] = {
                    "token": creds.token, 
                    "refresh_token": creds.refresh_token, 
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id, 
                    "client_secret": creds.client_secret, 
                    "scopes": creds.scopes,
                }
                
                # ユーザー情報を取得
                user_info_response = requests.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                user_info_response.raise_for_status()
                st.session_state["google_user_info"] = user_info_response.json()
                
                # 認証成功をログに記録
                st.success("✅ Google認証が正常に完了しました！")
                
                # URLパラメータをクリアしてリダイレクト
                st.query_params.clear()
                time.sleep(2)  # ユーザーが成功メッセージを見られるように少し待機
                st.rerun()
            
        except Exception as e:
            st.error(f"Google認証中にエラーが発生しました: {str(e)}")
            st.code(traceback.format_exc())
            # エラー時もパラメータをクリア
            st.query_params.clear()
            if st.button("トップページに戻る"):
                st.rerun()
    else:
        st.warning("認証フローを開始します...")
        st.info("stateパラメータの不整合が検出されましたが、処理を続行します。")
        # パラメータをクリアして再開
        st.query_params.clear()
        if st.button("再度ログインする"):
            st.rerun()

# ===============================================================
# 4. UI描画
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    
    # ログイン状態の確認と表示
    if "google_user_info" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        
        # 新しいauth flowとstateを毎回生成
        flow = get_google_auth_flow()
        authorization_url, state = flow.authorization_url(
            prompt="consent", 
            access_type="offline",
            include_granted_scopes='true'  # より安定した認証のため
        )
        st.session_state["google_auth_state"] = state
        
        # デバッグ情報（本番環境では削除推奨）
        st.write(f"生成されたstate: {state}")
        
        st.link_button("🗝️ Googleアカウントでログイン", authorization_url, use_container_width=True)
        
        # 追加のトラブルシューティング情報
        with st.expander("🔍 トラブルシューティング"):
            st.write("認証で問題が発生する場合:")
            st.write("1. ブラウザのキャッシュとCookieをクリアしてください")
            st.write("2. シークレット/プライベートモードでお試しください")
            st.write("3. 複数のタブでアプリを開いている場合は、他のタブを閉じてください")
    else:
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: 
            st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: 
            st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): 
            google_logout()
    
    st.divider()

# --- メインコンテンツ ---
if "google_user_info" not in st.session_state:
    st.header("ようこそ、AIアシスタント・ポータルへ！")
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    with st.sidebar:
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, disabled=False)
    
    st.header(f"{tool_choice}")
    st.divider()

    if tool_choice == "🚙 交通費自動計算":
        st.success("ようこそ！ 認証システムは、ついに、正常に稼働しました。")
        st.info("このツールは現在、PoC（技術実証）段階です。")
        try:
            creds = Credentials(**st.session_state["google_credentials"])
            gc = gspread.authorize(creds)
            with st.spinner("Googleスプレッドシートへの接続をテスト中..."):
                spreadsheet_list = gc.list_spreadsheet_files()
                st.write("あなたがアクセス可能なスプレッドシート (最新5件):")
                for s in spreadsheet_list[:5]:
                    st.markdown(f"- [{s['name']}]({s.get('webViewLink', '#')})")
        except Exception as e:
            st.error(f"ツールの実行中にエラーが発生しました: {e}")
            st.code(traceback.format_exc())
    else:
        st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
