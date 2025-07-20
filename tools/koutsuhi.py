# tools/koutsuhi.py (最後の武器"departure_time"搭載 最終決戦仕様)

import streamlit as st
import googlemaps
import google.generativeai as genai
import traceback
import time
from streamlit_local_storage import LocalStorage
import re
import json
from datetime import datetime # ★★★ 最後の武器をインポート ★★★

# ------------------------------------------------
# APIキー管理の心臓部（変更なし）
# ------------------------------------------------
def get_user_api_keys():
    localS = LocalStorage()
    maps_key_data = localS.getItem("user_gmaps_api_key")
    gemini_key_data = localS.getItem("user_gemini_api_key")
    maps_key = maps_key_data.get("value") if isinstance(maps_key_data, dict) else maps_key_data
    gemini_key = gemini_key_data.get("value") if isinstance(gemini_key_data, dict) else gemini_key_data
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定")
        if maps_key and gemini_key:
            st.success("✅ 全てのAPIキーが設定済みです。")
            if st.button("🔄 APIキーを再設定する"):
                localS.setItem("user_gmaps_api_key", None, key="maps_reset")
                localS.setItem("user_gemini_api_key", None, key="gemini_reset")
                st.rerun()
            return maps_key, gemini_key
        else:
            st.warning("⚠️ APIキーが設定されていません。")
            with st.form("api_keys_form"):
                st.info("このツールには、2つのAPIキーが必要です。")
                new_maps_key = st.text_input("あなたのGoogle Maps APIキー", type="password", value=maps_key or "")
                new_gemini_key = st.text_input("あなたのGemini APIキー", type="password", value=gemini_key or "")
                submitted = st.form_submit_button("🔐 これらのキーを記憶させる")
                if submitted:
                    if not new_maps_key or not new_gemini_key: st.error("❌ 両方のAPIキーを入力してください。")
                    else:
                        localS.setItem("user_gmaps_api_key", {"value": new_maps_key.strip()}, key="maps_set")
                        localS.setItem("user_gemini_api_key", {"value": new_gemini_key.strip()}, key="gemini_set")
                        st.success("✅ キーを記憶しました！")
                        time.sleep(1); st.rerun()
            return None, None

# ------------------------------------------------
# 場所特定のAI頭脳（変更なし）
# ------------------------------------------------
def find_best_place(gmaps, query):
    if not query: return None, "入力が空です。"
    try:
        places_result = gmaps.places(query=query, language="ja", region="JP", type="transit_station")
        if places_result and places_result.get("status") == "OK": return places_result["results"][0], None
        places_result = gmaps.places(query=query, language="ja", region="JP")
        if places_result and places_result.get("status") == "OK": return places_result["results"][0], None
        return None, f"「{query}」に一致する場所が見つかりませんでした。"
    except Exception as e: return None, f"場所の検索中にエラーが発生しました: {e}"

# ------------------------------------------------
# AIへの指示書（プロンプト）（変更なし）
# ------------------------------------------------
def generate_ai_transit_summary(gemini_key, directions_result):
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        あなたは、日本の交通事情に精通した、世界最高の旅行コンシェルジュです。提供されたGoogle Maps APIのJSONデータを元に、ユーザーが心から「分かりやすい！」と感じる、最高の乗り換え案内を生成してください。
        # 指示
        1. JSONデータから、旅行の「総所要時間」と、もし存在するなら「運賃(fare)」を抽出し、最初に明確に提示してください。
        2. 次に「経路案内」として、ステップごとの具体的な指示を、番号付きリストで作成してください。
        3. 各ステップは、`travel_mode`に応じて、以下の形式で、絵文字を使いながら表現してください。
           - **TRANSIT（公共交通機関）の場合:** `line.name`(路線名)と`line.vehicle.name`(乗り物の種類)を表示してください。`departure_stop.name`(出発駅)と`arrival_stop.name`(到着駅)、そして`num_stops`(駅数)を必ず含めてください。
           - **WALKING（徒歩）の場合:** `html_instructions`(指示)と`distance.text`(距離)を簡潔にまとめてください。
        4. 全体を通して、非常に親切で、丁寧な言葉遣いを徹底してください。
        5. 出力は、Streamlitで美しく表示できる、Markdown形式でお願いします。
        6. JSONデータにない情報は、絶対に創作しないでください。データに忠実に行動してください。
        # Google Maps APIのJSONデータ
        ```json
        {json.dumps(directions_result, ensure_ascii=False, indent=2)}
        ```
        """
        response = model.generate_content(prompt)
        return response.text, None
    except Exception as e: return None, f"AIによる要約生成中にエラーが発生しました: {e}"

# ------------------------------------------------
# ツールの本体
# ------------------------------------------------
def show_tool():
    maps_key, gemini_key = get_user_api_keys()
    if maps_key and gemini_key:
        st.info("🤖 出発地と目的地の駅名や住所を、自由に入力してください。AIが最適な場所とルートを提案します。")
        st.markdown("---")
        with st.form("distance_form"):
            origin_query = st.text_input("🚩 出発地", placeholder="例：小阪、新宿、大阪城公園")
            destination_query = st.text_input("🎯 目的地", placeholder="例：布施、東京駅、ディズニーランド")
            submit_button = st.form_submit_button(label="🔍 AIにルートを尋ねる")
        if submit_button:
            if not origin_query or not destination_query: st.warning("⚠️ 出発地と目的地の両方を入力してください。"); return
            with st.spinner("🤖 2人のAIアシスタントが、協力して最適なルートを検索中です..."):
                try:
                    gmaps = googlemaps.Client(key=maps_key)
                    origin_place, origin_error = find_best_place(gmaps, origin_query)
                    if origin_error: st.error(f"出発地エラー: {origin_error}"); return
                    destination_place, dest_error = find_best_place(gmaps, destination_query)
                    if dest_error: st.error(f"目的地エラー: {dest_error}"); return
                    origin_address = origin_place['formatted_address']
                    destination_address = destination_place['formatted_address']
                    
                    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
                    # ★★★ これが、GoogleのAIに、一切の言い訳をさせない、 ★★★
                    # ★★★           最後の、そして究極の命令です！         ★★★
                    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
                    directions_result = gmaps.directions(
                        origin=origin_address, 
                        destination=destination_address, 
                        mode="transit", 
                        language="ja",
                        departure_time=datetime.now() # 「今」出発するという、絶対的な命令！
                    )
                    
                    if not directions_result: st.error("❌ 指定された場所間の公共交通機関ルートが見つかりませんでした。"); return
                    summary, error = generate_ai_transit_summary(gemini_key, directions_result)
                    if error:
                        st.error(error)
                        with st.expander("元のAPIデータを見る"): st.json(directions_result)
                    else:
                        st.success("✅ AIによる乗り換え案内が完成しました！")
                        st.markdown(summary)
                except Exception as e:
                    st.error("⚠️ 処理中に予期しないエラーが発生しました。")
                    st.code(traceback.format_exc())
    else:
        st.info("👆 サイドバーで、ご自身のAPIキーを設定してください。")
