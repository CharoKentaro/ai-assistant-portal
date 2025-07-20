import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import requests
import traceback
import time
from streamlit_local_storage import LocalStorage

# --- 専門家のインポート ---
from tools import koutsuhi, calendar_tool, transcript_tool, research_tool

# ===============================================================
# 1. アプリの基本設定と、神聖なる金庫からの情報取得
# ===============================================================
st.set_page_config(
    page_title="AIアシスタント・ポータル", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="expanded"  # モバイルでサイドバーを展開
)

try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    SCOPE = [
        "openid", 
        "https://www.googleapis.com/auth/userinfo.email", 
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
except (KeyError, FileNotFoundError):
    st.error("重大なエラー: StreamlitのSecretsにGoogle認証情報が設定されていません。")
    st.stop()

# ===============================================================
# 2. ログイン/ログアウト関数（モバイル対応版）
# ===============================================================
def get_google_auth_flow():
    """Google OAuth フローを正しく初期化（モバイル対応）"""
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [REDIRECT_URI]
        }
    }
    
    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=SCOPE
    )
    
    # リダイレクトURIを明示的に設定
    flow.redirect_uri = REDIRECT_URI
    
    return flow

def google_logout():
    """ログアウト処理"""
    keys_to_clear = ["google_credentials", "google_user_info", "google_auth_state"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 3. 認証処理の核心部（モバイル対応強化版）
# ===============================================================
if "code" in st.query_params and "google_credentials" not in st.session_state:
    query_state = st.query_params.get("state")
    session_state = st.session_state.get("google_auth_state")
    
    # セッションステートのチェックを厳密に行う
    if query_state and session_state and query_state == session_state:
        try:
            with st.spinner("Google認証処理中..."):
                flow = get_google_auth_flow()
                
                try:
                    # 認証コードを使ってトークンを取得
                    flow.fetch_token(code=st.query_params["code"])
                except Exception as token_error:
                    # スコープ変更エラーの場合の処理
                    if "Scope has changed" in str(token_error):
                        st.warning("スコープが変更されました。再認証を試行します...")
                        flow = Flow.from_client_config(
                            client_config={
                                "web": {
                                    "client_id": CLIENT_ID,
                                    "client_secret": CLIENT_SECRET,
                                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                    "token_uri": "https://oauth2.googleapis.com/token",
                                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                                    "redirect_uris": [REDIRECT_URI]
                                }
                            },
                            scopes=None
                        )
                        flow.redirect_uri = REDIRECT_URI
                        flow.fetch_token(code=st.query_params["code"])
                    else:
                        raise token_error
                
                creds = flow.credentials
                
                # 認証情報をセッションに保存
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
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"}
                )
                user_info_response.raise_for_status()
                st.session_state["google_user_info"] = user_info_response.json()
                
                st.success("✅ Google認証が正常に完了しました！")
                
                # クエリパラメータをクリア
                st.query_params.clear()
                
                # モバイル環境での安定性を向上
                time.sleep(2)  # 少し長めの待機時間
                st.rerun()
                
        except Exception as e:
            st.error(f"Google認証中にエラーが発生しました: {str(e)}")
            st.code(traceback.format_exc())
            st.query_params.clear()
            if st.button("トップページに戻る", use_container_width=True):
                st.rerun()
    else:
        st.warning("認証フローを再開します...")
        st.query_params.clear()
        st.rerun()

# ===============================================================
# 4. UI描画（モバイル最適化版）
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    
    if "google_user_info" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        
        try:
            flow = get_google_auth_flow()
            
            # 認証URLを生成（モバイル対応の修正）
            authorization_url, state = flow.authorization_url(
                prompt="consent",
                access_type="offline",
                include_granted_scopes=True  # ブール値として正しく指定
            )
            
            # セッションにstateを保存
            st.session_state["google_auth_state"] = state
            
            # モバイル対応のログインボタン
            st.link_button(
                "🗝️ Googleアカウントでログイン", 
                authorization_url, 
                use_container_width=True
            )
            
            # モバイル環境での代替手段も提供
            with st.expander("🔧 うまくログインできない場合"):
                st.markdown(f"""
                以下のリンクを直接コピーしてブラウザで開いてください：
                
                {authorization_url}
                """)
            
        except Exception as e:
            st.error(f"認証フローの初期化中にエラーが発生しました: {str(e)}")
            st.code(traceback.format_exc())
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

    # ツール選択（ログイン後のみ）
    if "google_user_info" in st.session_state:
        tool_options = ("📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換け案内")
        tool_choice = st.radio(
            "使いたいツールを選んでください:", 
            tool_options, 
            key="tool_choice_radio"
        )
        
        st.divider()
        st.header("⚙️ APIキー設定")
        
        # ローカルストレージのエラーハンドリング強化
        try:
            localS = LocalStorage()
            saved_keys = localS.getItem("api_keys")
            
            gemini_default = saved_keys.get('gemini', '') if isinstance(saved_keys, dict) else ""
            speech_default = saved_keys.get('speech', '') if isinstance(saved_keys, dict) else ""
            
        except Exception as e:
            st.warning(f"ローカルストレージの読み込み中にエラーが発生しました: {str(e)}")
            gemini_default = ""
            speech_default = ""
        
        gemini_api_key = st.text_input(
            "1. Gemini APIキー", 
            type="password", 
            value=gemini_default, 
            help="Google AI Studioで取得したキー"
        )
        
        speech_api_key = st.text_input(
            "2. Speech-to-Text APIキー", 
            type="password", 
            value=speech_default, 
            help="Google Cloud Platformで取得したキー"
        )
        
        if st.button("APIキーをこのブラウザに保存する", use_container_width=True):
            try:
                localS = LocalStorage()
                localS.setItem("api_keys", {
                    "gemini": gemini_api_key, 
                    "speech": speech_api_key
                })
                st.success("キーを保存しました！")
            except Exception as e:
                st.error(f"キーの保存中にエラーが発生しました: {str(e)}")
                st.info("セッション中は入力されたキーが保持されます。")
        
        # リンクをモバイル対応に改善
        st.markdown("""
        <div style="font-size: 0.9em;">
            <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">
                1. Gemini APIキーの取得 ↗
            </a><br>
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener">
                2. Speech-to-Text APIキーの取得 ↗
            </a>
        </div>
        """, unsafe_allow_html=True)

# ===============================================================
# 5. メインコンテンツ（モバイル最適化）
# ===============================================================
if "google_user_info" not in st.session_state:
    st.header("ようこそ、AIアシスタント・ポータルへ！")
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
    
    # モバイル環境での注意事項
    with st.expander("📱 モバイル環境でのご利用について"):
        st.markdown("""
        **スマートフォンでのログインがうまくいかない場合：**
        
        1. **ブラウザのキャッシュをクリア**してから再度お試しください
        2. **シークレット/プライベートモード**での利用をお試しください
        3. **別のブラウザ**（Chrome、Safari、Firefoxなど）でお試しください
        4. サイドバーの「うまくログインできない場合」セクションのリンクを直接使用してください
        
        **推奨ブラウザ：** Chrome（Android）、Safari（iOS）
        """)
else:
    tool_choice = st.session_state.get("tool_choice_radio")
    if tool_choice:
        st.header(f"{tool_choice}")
        st.divider()

        # 各ツールの呼び出し
        if tool_choice == "🚇 AI乗り換え案内":
            koutsuhi.show_tool()
        elif tool_choice == "📅 カレンダー登録":
            calendar_tool.show_tool(
                gemini_api_key=gemini_api_key, 
                speech_api_key=speech_api_key
            )
        elif tool_choice == "📝 議事録作成":
            transcript_tool.show_tool(speech_api_key=speech_api_key)
        elif tool_choice == "💹 価格リサーチ":
            research_tool.show_tool(gemini_api_key=gemini_api_key)
        else:
            st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
    else:
        st.header("ツールを選択してください")
        st.info("サイドバーからご利用になりたいツールを選択してください。")
        
        # モバイル環境での操作ガイド
        if st.button("📱 サイドバーを開く", help="モバイル環境でサイドバーが見えない場合はこちら"):
            st.info("画面左上の「>」アイコンをタップしてサイドバーを開いてください。")
