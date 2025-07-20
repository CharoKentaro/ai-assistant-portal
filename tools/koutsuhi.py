# tools/koutsuhi.py (最終完成版 - "電車だけ" を検索するAI搭載)

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage
import re

# ------------------------------------------------
# APIキー管理の心臓部（変更なし）
# ------------------------------------------------
def get_user_api_key():
    localS = LocalStorage()
    saved_key_data = localS.getItem("user_gmaps_api_key")
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定")
        key_value = None
        if isinstance(saved_key_data, dict) and saved_key_data.get("value"):
            key_value = saved_key_data["value"]
        elif isinstance(saved_key_data, str) and saved_key_data:
            key_value = saved_key_data
        if key_value:
            st.success("✅ APIキーは設定済みです。")
            if st.button("🔄 APIキーを変更・削除する"):
                localS.setItem("user_gmaps_api_key", None)
                st.rerun()
            return key_value
        else:
            st.warning("⚠️ Google Maps APIキーが設定されていません。")
            with st.form("api_key_form"):
                st.info("💡 下の入力欄にご自身のAPIキーを入力してください。")
                new_key = st.text_input("あなたのGoogle Maps APIキー", type="password")
                submitted = st.form_submit_button("🔐 このAPIキーを記憶させる")
                if submitted:
                    if not new_key or len(new_key.strip()) < 20: st.error("❌ 有効なAPIキーを入力してください。")
                    else:
                        localS.setItem("user_gmaps_api_key", {"value": new_key.strip()})
                        st.success("✅ キーを記憶しました！")
                        time.sleep(1); st.rerun()
            return None

# ------------------------------------------------
# 場所特定のAI頭脳（変更なし）
# ------------------------------------------------
def find_best_place(gmaps, query):
    if not query: return None, "入力が空です。"
    try:
        places_result = gmaps.places(query=query, language="ja", region="JP")
        if places_result and places_result.get("status") == "OK":
            return places_result["results"][0], None
        return None, f"「{query}」に一致する場所が見つかりませんでした。"
    except Exception as e:
        return None, f"場所の検索中にエラーが発生しました: {e}"

# ------------------------------------------------
# 乗り換え案内を美しく表示する関数（変更なし）
# ------------------------------------------------
def display_transit_details(leg):
    st.success("✅ ルートが見つかりました！")
    col1, col2 = st.columns(2)
    col1.metric("⏱️ 総所要時間", leg['duration']['text'])
    if 'fare' in leg: col2.metric("💰 片道運賃", leg['fare']['text'])
    else: col2.metric("📏 総移動距離", leg['distance']['text'])
    st.markdown("---"); st.subheader("経路案内")
    for i, step in enumerate(leg['steps']):
        clean_instruction = re.sub('<.*?>', '', step['html_instructions'])
        with st.container(border=True):
            if step['travel_mode'] == 'TRANSIT':
                details = step['transit_details']
                line_info = details['line']
                line_icon = line_info.get('vehicle', {}).get('icon', '🚇')
                line_name = line_info.get('name', '不明な路線')
                departure_station = details['departure_stop']['name']
                arrival_station = details['arrival_stop']['name']
                num_stops = details.get('num_stops', '?')
                st.markdown(f"**{i+1}. {line_icon} {line_name}** に乗車")
                st.markdown(f"    **出発:** {departure_station}")
                st.markdown(f"    **到着:** {arrival_station} ({num_stops} 駅)")
            elif step['travel_mode'] == 'WALKING':
                st.markdown(f"**{i+1}. 🚶 徒歩** ({clean_instruction}, {step['distance']['text']})")

# ------------------------------------------------
# ツールの本体
# ------------------------------------------------
def show_tool():
    user_api_key = get_user_api_key()
    if user_api_key:
        st.info("🤖 出発地と目的地の駅名や住所を、自由に入力してください。AIが最適な場所を推測します。")
        st.markdown("---")
        with st.form("distance_form"):
            origin_query = st.text_input("🚩 出発地", placeholder="例：小阪、新宿、大阪城公園")
            destination_query = st.text_input("🎯 目的地", placeholder="例：布施、東京駅、ディズニーランド")
            transport_mode = st.selectbox(
                "移動手段", options=["transit", "driving", "walking"],
                format_func=lambda x: {"transit": "🚇 公共交通機関", "driving": "🚗 車", "walking": "🚶 徒歩"}[x],
                index=0
            )
            submit_button = st.form_submit_button(label="🔍 ルートを検索する")

        if submit_button:
            if not origin_query or not destination_query: st.warning("⚠️ 出発地と目的地の両方を入力してください。"); return
            with st.spinner("🤖 AIが最適な電車ルートを検索中..."):
                try:
                    gmaps = googlemaps.Client(key=user_api_key)
                    origin_place, origin_error = find_best_place(gmaps, origin_query)
                    if origin_error: st.error(f"出発地エラー: {origin_error}"); return
                    destination_place, dest_error = find_best_place(gmaps, destination_query)
                    if dest_error: st.error(f"目的地エラー: {dest_error}"); return
                    
                    origin_address = origin_place['formatted_address']
                    destination_address = destination_place['formatted_address']
                    st.info(f"🔄 **出発地:** {origin_address}")
                    st.info(f"🔄 **目的地:** {destination_address}")

                    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
                    # ★★★ ここが、私たちの魂を宿らせる、最後の魔法です ★★★
                    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
                    directions_result = gmaps.directions(
                        origin=origin_address, 
                        destination=destination_address, 
                        mode=transport_mode, 
                        language="ja",
                        # 「電車」でのルートだけを要求する、という強い意志表示！
                        transit_mode=["train", "rail"] 
                    )
                    
                    if directions_result:
                        leg = directions_result[0]['legs'][0]
                        if transport_mode == 'transit': display_transit_details(leg)
                        else:
                            st.success("✅ ルートが見つかりました！")
                            col1, col2 = st.columns(2)
                            col1.metric("📏 総移動距離", leg['distance']['text'])
                            col2.metric("⏱️ 予想所要時間", leg['duration']['text'])
                    else: st.error("❌ 指定された場所間のルートが見つかりませんでした。")
                except Exception as e:
                    st.error("⚠️ 処理中に予期しないエラーが発生しました。")
                    st.code(traceback.format_exc())
    else:
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
