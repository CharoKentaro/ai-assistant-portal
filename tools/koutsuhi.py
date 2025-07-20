# tools/koutsuhi.py (最終進化版 - 真の乗り換え案内機能搭載)

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage
import re # HTMLタグ除去のためにインポート

# ------------------------------------------------
# APIキー管理の心臓部（ここは既に完璧なので変更なし）
# ------------------------------------------------
def get_user_api_key():
    # ... (この関数の中身は、前回と全く同じなので省略します) ...
    # ... (実際のファイルでは、この部分のコードは消さずに、そのままにしてください) ...
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
            st.success("✅ APIキーは設定済みです。")
            masked_key = key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "設定済み"
            st.caption(f"現在のキー: {masked_key}")
            if st.button("🔄 APIキーを変更・削除する"):
                localS.setItem("user_gmaps_api_key", None)
                st.success("🗑️ APIキーを削除しました。ページを更新します...")
                time.sleep(1)
                st.rerun()
            return key_value
        else:
            st.warning("⚠️ Google Maps APIキーが設定されていません。")
            with st.form("api_key_form"):
                st.info("💡 下の入力欄にご自身のAPIキーを入力してください。")
                new_key = st.text_input("あなたのGoogle Maps APIキー", type="password")
                submitted = st.form_submit_button("🔐 このAPIキーをブラウザに記憶させる")
                if submitted:
                    if not new_key or len(new_key.strip()) < 20:
                        st.error("❌ 有効なAPIキーを入力してください。")
                    else:
                        localS.setItem("user_gmaps_api_key", {"value": new_key.strip()})
                        st.success("✅ キーを記憶しました！ページを更新します...")
                        time.sleep(1)
                        st.rerun()
            return None

# ------------------------------------------------
# 駅名補完・場所特定のAI頭脳（ここは変更なし）
# ------------------------------------------------
def expand_station_name(address):
    # ... (この関数も、前回と全く同じなので省略します) ...
    # ... (実際のファイルでは、この部分のコードは消さずに、そのままにしてください) ...
    if not address: return address
    station_expansions = { "小阪": "河内小阪駅", "八戸ノ里": "八戸ノ里駅", "布施": "布施駅", "鶴橋": "鶴橋駅", "今里": "今里駅", "新深江": "新深江駅", "小路": "小路駅", "若江岩田": "若江岩田駅", "河内花園": "河内花園駅", "東花園": "東花園駅", "瓢箪山": "瓢箪山駅", "枚岡": "枚岡駅", "額田": "額田駅", "石切": "石切駅", "生駒": "生駒駅", "大阪": "大阪駅", "梅田": "梅田駅", "天王寺": "天王寺駅", "難波": "難波駅", "なんば": "難波駅", "心斎橋": "心斎橋駅", "本町": "本町駅", "淀屋橋": "淀屋橋駅", "京橋": "京橋駅", "新大阪": "新大阪駅", "西九条": "西九条駅", "弁天町": "弁天町駅", "京都": "京都駅", "神戸": "神戸駅", "三宮": "三宮駅", "奈良": "奈良駅", "和歌山": "和歌山駅", "東京": "東京駅", "新宿": "新宿駅", "渋谷": "渋谷駅", "池袋": "池袋駅", "品川": "品川駅", "上野": "上野駅", "秋葉原": "秋葉原駅", "有楽町": "有楽町駅", "銀座": "銀座駅", "六本木": "六本木駅", "名古屋": "名古屋駅", "博多": "博多駅", "札幌": "札幌駅", "仙台": "仙台駅", "広島": "広島駅", "福岡": "博多駅" }
    address_clean = address.strip()
    if "駅" in address or "station" in address.lower(): return address
    if address_clean in station_expansions: return station_expansions[address_clean]
    for short_name, full_name in station_expansions.items():
        if short_name in address_clean: return address.replace(short_name, full_name)
    if re.search(r'[ひ-ゟヲ-ヿ一-鿿]$', address_clean): return f"{address_clean}駅"
    return address

def find_best_place(gmaps, query):
    # ... (この関数も、前回と全く同じなので省略します) ...
    # ... (実際のファイルでは、この部分のコードは消さずに、そのままにしてください) ...
    if not query: return None, "入力が空です。"
    try:
        expanded_query = expand_station_name(query)
        places_result = gmaps.places(query=expanded_query, language="ja", region="JP")
        if places_result and places_result.get("status") == "OK" and places_result.get("results"):
            return places_result["results"][0], None
        else:
            try:
                geocode_result = gmaps.geocode(expanded_query, region="JP", language="ja")
                if geocode_result:
                    place_info = {'formatted_address': geocode_result[0]['formatted_address'], 'geometry': geocode_result[0]['geometry'], 'name': expanded_query}
                    return place_info, None
            except: pass
            return None, f"「{query}」に一致する場所が見つかりませんでした。"
    except Exception as e: return None, f"場所の検索中にエラーが発生しました: {e}"


# ------------------------------------------------
# ★★★ ここからが、今回、魂を吹き込んだ部分です ★★★
# ------------------------------------------------
def display_transit_details(leg):
    """公共交通機関の詳細情報を、美しく表示する関数"""
    
    st.success("✅ ルートが見つかりました！")
    
    # 1. サマリー情報を表示
    col1, col2 = st.columns(2)
    col1.metric("⏱️ 総所要時間", leg['duration']['text'])
    
    # 公共交通機関の場合、運賃情報があれば表示
    if 'fare' in leg:
        col2.metric("💰 片道運賃", leg['fare']['text'])
    else:
        col2.metric("📏 総移動距離", leg['distance']['text'])

    # 2. 乗り換えステップを一つずつ表示
    st.markdown("---")
    st.subheader("経路案内")

    for i, step in enumerate(leg['steps']):
        # HTMLタグを掃除する
        clean_instruction = re.sub('<.*?>', '', step['html_instructions'])
        
        # 乗り換えか、徒歩か
        if step['travel_mode'] == 'TRANSIT':
            details = step['transit_details']
            line_info = details['line']
            
            # 電車のアイコンと路線名
            line_icon = line_info.get('vehicle', {}).get('icon', '🚇')
            line_name = line_info.get('name', '不明な路線')
            
            # 出発駅と到着駅
            departure_station = details['departure_stop']['name']
            arrival_station = details['arrival_stop']['name']
            num_stops = details.get('num_stops', '?')

            with st.container(border=True):
                st.markdown(f"**{i+1}. {line_icon} {line_name}** に乗車")
                st.markdown(f"   - **出発:** {departure_station}")
                st.markdown(f"   - **到着:** {arrival_station} ({num_stops} 駅)")
                st.caption(f"   時間: {step['duration']['text']}")

        elif step['travel_mode'] == 'WALKING':
            with st.container(border=True):
                 st.markdown(f"**{i+1}. 🚶 徒歩**")
                 st.markdown(f"   - {clean_instruction} ({step['distance']['text']})")
                 st.caption(f"   時間: {step['duration']['text']}")

def show_tool():
    """AI乗り換え案内ツールを表示・実行するメイン関数"""

    # ★ 修正点①：重複していたヘッダーを削除！
    # st.header("🚇 AI乗り換え案内") は、app.pyに任せる

    user_api_key = get_user_api_key()
    
    if user_api_key:
        st.info("🤖 出発地と目的地の駅名や住所を、自由に入力してください。AIが最適な場所を推測します。")
        st.markdown("---")

        with st.form("distance_form"):
            origin_query = st.text_input("🚩 出発地", placeholder="例：小阪、新宿、大阪城公園")
            destination_query = st.text_input("🎯 目的地", placeholder="例：布施、東京駅、ディズニーランド")
            
            # ★ 修正点②：デフォルトを「公共交通機関」に設定！
            transport_mode = st.selectbox(
                "移動手段",
                options=["transit", "driving", "walking", "bicycling"],
                format_func=lambda x: {"transit": "🚇 公共交通機関", "driving": "🚗 車", "walking": "🚶 徒歩", "bicycling": "🚲 自転車"}[x],
                index=0 # index=0 はリストの最初のアイテム（transit）を意味する
            )
            submit_button = st.form_submit_button(label="🔍 ルートを検索する")

        if submit_button:
            if not origin_query or not destination_query:
                st.warning("⚠️ 出発地と目的地の両方を入力してください。")
            else:
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

                        directions_result = gmaps.directions(origin=origin_address, destination=destination_address, mode=transport_mode, language="ja")
                        
                        # ★ 修正点③：結果の表示方法を、賢く切り替える！
                        if directions_result:
                            leg = directions_result[0]['legs'][0]
                            # 公共交通機関モードの場合は、新しい詳細表示関数を呼び出す
                            if transport_mode == 'transit':
                                display_transit_details(leg)
                            else:
                                # それ以外のモードは、従来通りのシンプルな表示
                                st.success("✅ ルートが見つかりました！")
                                col1, col2 = st.columns(2)
                                col1.metric("📏 総移動距離", leg['distance']['text'])
                                col2.metric("⏱️ 予想所要時間", leg['duration']['text'])
                        else:
                            st.error("❌ 指定された場所間のルートが見つかりませんでした。")
                    except Exception as e:
                        st.error("⚠️ 処理中に予期しないエラーが発生しました。")
                        st.code(traceback.format_exc())
    else:
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
