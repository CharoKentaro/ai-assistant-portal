# tools/koutsuhi.py

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage

# ------------------------------------------------
# ★★★ APIキーを管理する、このファイルの心臓部 ★★★
# ------------------------------------------------
def get_user_api_key():
    """
    ユーザーのブラウザにAPIキーを保存・管理し、そのキーを返す関数。
    - キーが保存されていれば、その値を返す。
    - 保存されていなければ、サイドバーに入力フォームを表示し、Noneを返す。
    """
    
    localS = LocalStorage()
    saved_key_data = localS.getItem("user_gmaps_api_key")
    
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定 (AI乗り換え案内)")
        
        # ----------------------------------------------------
        # ★★★ 今回のエラーを解決する、最も重要な部分 ★★★
        # 取得したデータが「辞書か」「ただの文字列か」を、丁寧に見極めるロジック
        # ----------------------------------------------------
        
        key_value = None
        # パターン①：データが「辞書」形式で、中に'value'キーがある（理想的な状態）
        if isinstance(saved_key_data, dict) and saved_key_data.get("value"):
            key_value = saved_key_data["value"]
        # パターン②：データが「文字列」として直接保存されている（以前のバージョンとの互換性のため）
        elif isinstance(saved_key_data, str) and saved_key_data:
            key_value = saved_key_data

        # --- 表示の分岐 ---
        # 有効なキーが見つかった場合
        if key_value:
            st.success("APIキーは設定済みです。")
            if st.button("APIキーを変更・削除する"):
                localS.removeItem("user_gmaps_api_key")
                st.rerun()
            return key_value

        # 有効なキーが見つからなかった場合（初回アクセスなど）
        else:
            st.warning("Google Maps APIキーが設定されていません。")
            with st.form("api_key_form"):
                st.info("下の入力欄にご自身のAPIキーを入力してください。キーは、あなたのブラウザ内にのみ安全に保存されます。")
                new_key = st.text_input("あなたのGoogle Maps APIキー", type="password")
                submitted = st.form_submit_button("このAPIキーをブラウザに記憶させる")
                
                if submitted:
                    if not new_key:
                        st.error("APIキーが入力されていません。")
                    else:
                        # ★★★ 今後は、必ずこの「辞書」形式で保存する ★★★
                        # これにより、将来の安定性が格段に向上します。
                        localS.setItem("user_gmaps_api_key", {"value": new_key})
                        st.success("キーを記憶しました！")
                        time.sleep(1) # ユーザーがメッセージを読むための、優しい待ち時間
                        st.rerun()
            
            return None

# ------------------------------------------------
# ★★★ ツールの本体 ★★★
# ------------------------------------------------
def show_tool():
    """AI乗り換え案内（交通費計算）ツールを表示・実行するメイン関数"""

    st.header("🚇 AI乗り換え案内")
    
    # まず、上記の関数を呼び出して、ユーザーのAPIキーを取得する
    user_api_key = get_user_api_key()
    
    # APIキーが正常に取得できた場合のみ、ツールの本体機能を表示する
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
                        gmaps = googlemaps.Client(key=user_api_key)
                        directions_result = gmaps.directions(origin, destination, mode="driving",region="JP")
                        
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
        # APIキーがまだ設定されていない場合の、親切な案内メッセージ
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
        with st.expander("APIキーとは？"):
            st.write("""
            このツールを動かすための「鍵」です。利用料金の公平性を保つため、利用者様ご自身でご用意いただいております。
            Google Cloud Platformで取得したAPIキーを、サイドバーで設定してください。
            設定したキーは、開発者には見えない形で、あなたのブラウザにのみ安全に保存されます。
            """)
