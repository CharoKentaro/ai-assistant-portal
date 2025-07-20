# tools/koutsuhi.py (AI搭載の最終完成版 - バグ修正済み)

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage

# ------------------------------------------------
# APIキーを管理する心臓部
# ------------------------------------------------
def get_user_api_key():
    localS = LocalStorage()
    saved_key_data = localS.getItem("user_gmaps_api_key")
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定 (AI乗り換え案内)")
        key_value = None
        if isinstance(saved_key_data, dict) and saved_key_data.get("value"):
            key_value = saved_key_data["value"]
        elif isinstance(saved_key_data, str) and saved_key_data:
            key_value = saved_key_data
        
        if key_value:
            st.success("APIキーは設定済みです。")
            if st.button("APIキーを変更・削除する"):
                # ★★★ ここが、私の間違いを修正した、唯一かつ重要な箇所です ★★★
                localS.setItem("user_gmaps_api_key", None) # removeItemではなく、中身をNoneにする
                st.rerun()
            return key_value
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
                        localS.setItem("user_gmaps_api_key", {"value": new_key})
                        st.success("キーを記憶しました！")
                        time.sleep(1)
                        st.rerun()
            return None

# ------------------------------------------------
# 曖昧な地名をGoogleのAIで特定する関数
# ------------------------------------------------
def find_best_place(gmaps, query):
    if not query: return None, "入力が空です。"
    try:
        places_result = gmaps.places(query=query, language="ja", region="JP")
        if places_result and places_result.get("status") == "OK":
            return places_result["results"][0], None
        else:
            return None, f"「{query}」に一致する場所が見つかりませんでした。"
    except Exception as e:
        return None, f"場所の検索中にエラーが発生しました: {e}"

# ------------------------------------------------
# ツールの本体
# ------------------------------------------------
def show_tool():
    st.header("🚇 AI乗り換え案内")
    user_api_key = get_user_api_key()
    
    if user_api_key:
        st.info("出発地と目的地の駅名や住所を、自由に入力してください。AIが最適な場所を推測します。")
        st.markdown("---")

        with st.form("distance_form"):
            origin_query = st.text_input("出発地", placeholder="例：小阪、新宿、大阪城公園")
            destination_query = st.text_input("目的地", placeholder="例：布施、東京駅、USJ")
            submit_button = st.form_submit_button(label="🚗 ルートを検索する")

        if submit_button:
            if not origin_query or not destination_query:
                st.warning("出発地と目的地の両方を入力してください。")
            else:
                with st.spinner("最適なルートをAIが検索中..."):
                    try:
                        gmaps = googlemaps.Client(key=user_api_key)
                        
                        origin_place, origin_error = find_best_place(gmaps, origin_query)
                        if origin_error: st.error(f"出発地の検索エラー: {origin_error}"); return

                        destination_place, dest_error = find_best_place(gmaps, destination_query)
                        if dest_error: st.error(f"目的地の検索エラー: {dest_error}"); return
                        
                        origin_address = origin_place['formatted_address']
                        destination_address = destination_place['formatted_address']
                        st.info(f"🔄 出発地を「{origin_address}」として検索します。")
                        st.info(f"🔄 目的地を「{destination_address}」として検索します。")

                        directions_result = gmaps.directions(origin=origin_address, destination=destination_address, mode="driving", language="ja")
                        
                        if directions_result:
                            leg = directions_result[0]['legs'][0]
                            st.success("✅ ルートが見つかりました！")
                            col1, col2 = st.columns(2)
                            col1.metric("総移動距離", leg['distance']['text'])
                            col2.metric("予想所要時間", leg['duration']['text'])
                        else:
                            st.error("ルートが見つかりませんでした。")
                    except Exception as e:
                        st.error("処理中に予期しないエラーが発生しました。")
                        st.error(f"詳細: {e}")
    else:
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
        with st.expander("🔑 APIキーと、必要なAPIについて"):
            st.markdown("...") # 省略
