# tools/koutsuhi.py (真・最終完成版 - 宝箱を開けるAI搭載)

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage
import re # HTMLタグを除去するためにインポート

# ------------------------------------------------
# APIキー管理の心臓部（ここは既に完璧です）
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
                    if not new_key or len(new_key.strip()) < 20:
                        st.error("❌ 有効なAPIキーを入力してください。")
                    else:
                        localS.setItem("user_gmaps_api_key", {"value": new_key.strip()})
                        st.success("✅ キーを記憶しました！")
                        time.sleep(1)
                        st.rerun()
            return None

# ------------------------------------------------
# ★★★ ここが、新しい「賢い頼み方」です ★★★
# ------------------------------------------------
def find_best_place(gmaps, query):
    """
    曖昧な地名から、まず「駅」を最優先で探し、なければ通常の場所を探す関数。
    """
    if not query: return None, "入力が空です。"
    try:
        # 1. まず「駅（transit_station）」タイプで、最優先検索
        places_result = gmaps.places(query=query, language="ja", region="JP", type="transit_station")
        if places_result and places_result.get("status") == "OK":
            return places_result["results"][0], None

        # 2. 駅で見つからなければ、タイプ指定なしで、もう一度探す（USJなどの施設のため）
        places_result = gmaps.places(query=query, language="ja", region="JP")
        if places_result and places_result.get("status") == "OK":
            return places_result["results"][0], None
            
        return None, f"「{query}」に一致する場所が見つかりませんでした。"
    except Exception as e:
        return None, f"場所の検索中にエラーが発生しました: {e}"

# ------------------------------------------------
# ★★★ そして、これが新しい「宝の取り出し方」です ★★★
# ------------------------------------------------
def display_transit_details(leg):
    """公共交通機関の「宝箱」を開けて、乗り換え詳細を美しく表示する関数"""
    
    st.success("✅ 電車のルートが見つかりました！")
    
    # サマリー情報（運賃と時間）
    col1, col2 = st.columns(2)
    col1.metric("⏱️ 総所要時間", leg['duration']['text'])
    if 'fare' in leg:
        col2.metric("💰 片道運賃", leg['fare']['text'])
    else:
        # 運賃情報がない場合は、距離を表示
        col2.metric("📏 総移動距離", leg['distance']['text'])

    st.markdown("---")
    st.subheader("経路案内")

    # 乗り換えの各ステップを、カード形式で表示
    for i, step in enumerate(leg['steps']):
        with st.container(border=True):
            # 乗り物の種類で表示を切り替え
            if step['travel_mode'] == 'TRANSIT':
                details = step['transit_details']
                line_info = details['line']
                
                # アイコンと路線名を取得
                line_icon = line_info.get('vehicle', {}).get('icon', '🚇')
                line_name = line_info.get('name', '不明な路線')
                line_color = line_info.get('color', '#808080') # 路線カラーがあれば取得
                
                # 駅情報
                departure_station = details['departure_stop']['name']
                arrival_station = details['arrival_stop']['name']
                num_stops = details.get('num_stops', '?')

                st.markdown(f"**{i+1}. <span style='color:{line_color};'>{line_icon} {line_name}</span>** に乗車", unsafe_allow_html=True)
                st.markdown(f"    **出発:** {departure_station}")
                st.markdown(f"    **到着:** {arrival_station} ({num_stops} 駅)")
                st.caption(f"    所要時間: {step['duration']['text']}")

            elif step['travel_mode'] == 'WALKING':
                # 徒歩区間の表示
                clean_instruction = re.sub('<.*?>', '', step['html_instructions'])
                st.markdown(f"**{i+1}. 🚶 徒歩** ({clean_instruction}, {step['distance']['text']})")
                st.caption(f"    所要時間: {step['duration']['text']}")

# ------------------------------------------------
# ツールの本体（これら新しい関数を呼び出すように修正）
# ------------------------------------------------
def show_tool():
    user_api_key = get_user_api_key()
    if user_api_key:
        st.info("🤖 出発地と目的地の駅名や住所を、自由に入力してください。AIが最適な場所を推測します。")
        st.markdown("---")
        with st.form("distance_form"):
            origin_query = st.text_input("🚩 出発地", placeholder="例：小阪、新宿、大阪城公園")
            destination_query = st.text_input("🎯 目的地", placeholder="例：布施、東京駅、ディズニーランド")
            submit_button = st.form_submit_button(label="🔍 ルートを検索する")

        if submit_button:
            if not origin_query or not destination_query: st.warning("⚠️ 出発地と目的地の両方を入力してください。"); return
            with st.spinner("🤖 AIが最適なルートを検索中..."):
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

                    directions_result = gmaps.directions(origin=origin_address, destination=destination_address, mode="transit", language="ja")
                    
                    if directions_result:
                        # 宝箱を開けて、新しい表示関数を呼び出す！
                        display_transit_details(directions_result[0]['legs'][0])
                    else:
                        st.error("❌ 指定された場所間のルートが見つかりませんでした。")
                except Exception as e:
                    st.error("⚠️ 処理中に予期しないエラーが発生しました。")
                    st.code(traceback.format_exc())
    else:
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
