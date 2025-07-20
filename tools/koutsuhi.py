# tools/koutsuhi.py (AI搭載の最終完成版)

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage

# ------------------------------------------------
# APIキーを管理する心臓部（この部分は変更なしで完璧です）
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
                localS.removeItem("user_gmaps_api_key")
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
# ★★★ ここからが、新しいAI頭脳の実装です ★★★
# ------------------------------------------------
def find_best_place(gmaps, query):
    """
    Places APIを使い、曖昧なクエリから最も可能性の高い場所を見つけ出す関数。
    """
    if not query:
        return None, f"入力が空です。"

    try:
        # Places API (Text Search) を呼び出す
        places_result = gmaps.places(
            query=query,
            language="ja",
            region="JP"
        )
        
        if places_result and places_result.get("status") == "OK":
            # 検索結果の最初の候補（最も関連性が高い）を返す
            return places_result["results"][0], None
        else:
            # 候補が見つからなかった場合
            return None, f"「{query}」に一致する場所が見つかりませんでした。"

    except Exception as e:
        return None, f"場所の検索中にエラーが発生しました: {e}"

# ------------------------------------------------
# ツールの本体
# ------------------------------------------------
def show_tool():
    """AI乗り換え案内ツールを表示・実行するメイン関数"""

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
                        
                        # 1. 出発地の最適な候補を検索
                        origin_place, origin_error = find_best_place(gmaps, origin_query)
                        if origin_error:
                            st.error(f"出発地の検索エラー: {origin_error}"); return

                        # 2. 目的地の最適な候補を検索
                        destination_place, dest_error = find_best_place(gmaps, destination_query)
                        if dest_error:
                            st.error(f"目的地の検索エラー: {dest_error}"); return
                        
                        # 3. 見つかった場所の正式名称を取得して、ユーザーに確認を促す
                        origin_address = origin_place['formatted_address']
                        destination_address = destination_place['formatted_address']
                        st.info(f"🔄 出発地を「{origin_address}」として検索します。")
                        st.info(f"🔄 目的地を「{destination_address}」として検索します。")

                        # 4. 正式名称を使って、ルートを検索
                        directions_result = gmaps.directions(
                            origin=origin_address, 
                            destination=destination_address, 
                            mode="driving", # または "transit" で公共交通機関
                            language="ja"
                        )
                        
                        if directions_result:
                            leg = directions_result[0]['legs'][0]
                            st.success("✅ ルートが見つかりました！")
                            col1, col2 = st.columns(2)
                            col1.metric("総移動距離", leg['distance']['text'])
                            col2.metric("予想所要時間", leg['duration']['text'])
                            st.markdown(f"**ルート概要:** {leg.get('summary', '詳細なし')}")
                        else:
                            st.error("ルートが見つかりませんでした。")

                    except Exception as e:
                        st.error("処理中に予期しないエラーが発生しました。")
                        st.error(f"詳細: {e}")
                        st.code(traceback.format_exc())
    else:
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
        with st.expander("🔑 APIキーと、必要なAPIについて"):
            st.markdown("""
            このツールは、以下のGoogle Maps APIを利用します。
            ご利用の際は、ご自身のGoogle Cloudプロジェクトで、**3つ全てのAPIが有効になっているか**をご確認ください。
            1.  **Directions API** (ルート検索)
            2.  **Geocoding API** (住所の変換)
            3.  **Places API** (場所の検索と特定)
            """)
