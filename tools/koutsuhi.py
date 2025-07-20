# tools/koutsuhi.py

import streamlit as st
import googlemaps
import traceback
# 参考コードと同様に、ローカルストレージを扱うための部品をインポート
from streamlit_local_storage import LocalStorage

# ------------------------------------------------
# ★★★ APIキーを管理する心臓部 ★★★
# 参考コードの「⑤ サイドバーと、APIキー入力」の思想を、さらに洗練させた関数
# ------------------------------------------------
def get_user_api_key():
    """ユーザーのブラウザにAPIキーを保存・管理し、そのキーを返す関数"""
    
    # 参考コードと同様に、LocalStorageのインスタンスを作成
    localS = LocalStorage()
    
    # ブラウザに保存されているキーを取得しようと試みる
    # 参考コードの localS.getItem("gemini_api_key") と同じ役割
    saved_key = localS.getItem("user_gmaps_api_key")
    
    # ----------------------------------------------------
    # 参考コードのUI部分を、私たちのアプリ用に最適化
    # ----------------------------------------------------
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定 (AI乗り換え案内)")
        
        # 【パターンA】キーが既に保存されている場合
        if saved_key and saved_key.get("value"):
            st.success("APIキーは設定済みです。")
            # ユーザーがキーを変更・削除したい場合のための便利なボタン
            if st.button("APIキーを変更・削除する"):
                localS.removeItem("user_gmaps_api_key")
                st.rerun() # 画面をリフレッシュして入力欄を再表示
            
            # 保存されているキーの値を、関数の戻り値として返す
            return saved_key["value"]

        # 【パターンB】キーがまだ保存されていない場合
        else:
            st.warning("Google Maps APIキーが設定されていません。")
            
            # 参考コードの st.text_input と st.button に相当する部分
            with st.form("api_key_form"):
                st.info("下の入力欄にご自身のAPIキーを入力してください。キーは、あなたのブラウザ内にのみ安全に保存されます。")
                new_key = st.text_input("あなたのGoogle Maps APIキー", type="password")
                submitted = st.form_submit_button("このAPIキーをブラウザに記憶させる")
                
                if submitted:
                    if not new_key:
                        st.error("APIキーが入力されていません。")
                    else:
                        # 入力されたキーをローカルストレージに保存
                        # 参考コードの localS.setItem(...) と同じ役割
                        localS.setItem("user_gmaps_api_key", new_key)
                        st.success("キーを記憶しました！")
                        st.rerun() # 画面をリフレッシュして成功表示に切り替え
            
            # キーが設定されるまで、ツールのメイン機能はここで停止
            return None

# ------------------------------------------------
# ツールのメイン関数
# ------------------------------------------------
def show_tool():
    """AI乗り換え案内（交通費計算）ツールを表示・実行する関数"""

    st.header("🚇 AI乗り換え案内")
    
    # ★★★ 最も重要なステップ ★★★
    # まず、上記の関数を呼び出して、ユーザーのAPIキーを取得しようと試みる
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
                with st.spinner(f"ルートを検索中..."):
                    try:
                        # ★★★ ここで、ユーザー自身のキーが使われる！ ★★★
                        gmaps = googlemaps.Client(key=user_api_key)
                        directions_result = gmaps.directions(origin, destination, mode="driving")
                        
                        if directions_result:
                            # (結果表示のロジック ... )
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
    else:
        # APIキーがまだ設定されていない場合の案内メッセージ
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
        with st.expander("APIキーとは？"):
            st.write("""
            このツールを動かすための「鍵」です。利用料金の公平性を保つため、利用者様ご自身でご用意いただいております。
            Google Cloud Platformで取得したAPIキーを、サイドバーで設定してください。
            設定したキーは、開発者には見えない形で、あなたのブラウザにのみ安全に保存されます。
            """)
