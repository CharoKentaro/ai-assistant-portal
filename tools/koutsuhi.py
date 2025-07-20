# tools/koutsuhi.py

import streamlit as st
import googlemaps
import traceback
from streamlit_local_storage import LocalStorage

# ------------------------------------------------
# ★★★ このファイルの核心部 ★★★
# ユーザーのブラウザにAPIキーを保存・管理するロジック
# ------------------------------------------------
def get_user_api_key():
    # ローカルストレージを初期化
    localS = LocalStorage()
    
    # 保存されているキーを取得しようと試みる
    saved_key = localS.getItem("user_gmaps_api_key")
    
    # サイドバーにAPIキー入力セクションを設ける
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定")
        
        # 保存されたキーが存在する場合の表示
        if saved_key and saved_key.get("value"):
            st.success("APIキーは設定済みです。")
            # ユーザーがキーを変更したい場合のために、ボタンを用意
            if st.button("APIキーを変更・削除する"):
                localS.removeItem("user_gmaps_api_key")
                st.rerun() # 画面をリフレッシュして入力欄を表示
            
            # 保存されているキーを返す
            return saved_key["value"]

        # 保存されたキーがない場合の表示
        else:
            st.warning("Google Maps APIキーが設定されていません。")
            st.info("下の入力欄に、ご自身のAPIキーを入力してください。キーは、あなたのブラウザ内にのみ安全に保存されます。")
            
            # ユーザーがキーを入力するためのフォーム
            with st.form("api_key_form"):
                new_key = st.text_input("あなたのGoogle Maps APIキー", type="password")
                submitted = st.form_submit_button("このキーを保存する")
                
                if submitted:
                    if not new_key:
                        st.error("APIキーが入力されていません。")
                    else:
                        # 入力されたキーをローカルストレージに保存
                        localS.setItem("user_gmaps_api_key", new_key)
                        st.rerun() # 画面をリフレッシュして成功表示に切り替え
            
            # APIキーが設定されるまで、ツールのメイン機能はここで停止
            return None

# ------------------------------------------------
# ツールのメイン関数
# ------------------------------------------------
def show_tool():
    """AI乗り換え案内（交通費計算）ツールを表示・実行する関数"""

    st.header("🚇 AI乗り換え案内")
    
    # まず、ユーザーのAPIキーを取得しようと試みる
    user_api_key = get_user_api_key()
    
    # APIキーが取得できた場合のみ、ツールの本体を表示する
    if user_api_key:
        st.info("出発地と目的地の住所を入力すると、実際の移動距離と所要時間を計算します。")
        st.markdown("---")

        with st.form("distance_form"):
            origin = st.text_input("出発地の住所", placeholder="例：東京駅")
            destination = st.text_input("目的地の住所", placeholder="例：大阪駅")
            submit_button = st.form_submit_button(label="🚗 距離と時間を計算する")

        if submit_button:
            if not origin or not destination:
                st.warning("出発地と目的地の両方を入力してください。")
            else:
                with st.spinner(f"「{origin}」から「{destination}」へのルートを検索中..."):
                    try:
                        gmaps = googlemaps.Client(key=user_api_key) # ★ユーザーのキーを使用
                        directions_result = gmaps.directions(origin, destination, mode="driving")
                        
                        if directions_result:
                            leg = directions_result[0]['legs'][0]
                            distance = leg['distance']['text']
                            duration = leg['duration']['text']
                            
                            st.success("✅ ルートが見つかりました！")
                            col1, col2 = st.columns(2)
                            col1.metric("総移動距離", distance)
                            col2.metric("予想所要時間", duration)
                            
                        else:
                            st.error("指定された住所間のルートが見つかりませんでした。")

                    except Exception as e:
                        st.error("APIの呼び出し中にエラーが発生しました。")
                        if "API key not valid" in str(e):
                             st.error("エラー：入力されたAPIキーが正しくないようです。サイドバーからキーを再設定してください。")
                        else:
                            st.error(f"エラー詳細: {e}")
                            st.code(traceback.format_exc())
    else:
        # APIキーがまだ設定されていない場合の案内
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
        with st.expander("APIキーとは？"):
            st.write("""
            Google Maps APIキーは、Google Mapsの様々な機能（経路検索など）をプログラムから利用するための「鍵」です。
            - このツールでは、利用料金の公平性を保つため、利用者様ご自身でAPIキーをご用意いただいております。
            - Google Cloud PlatformでAPIキーを取得し、サイドバーで設定してください。
            - 設定したキーは、開発者には見えない形で、あなたのブラウザにのみ保存されます。
            """)
