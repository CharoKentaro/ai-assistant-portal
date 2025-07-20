# tools/koutsuhi.py (AIへの最終命令仕様 - これが最後のコードです)

import streamlit as st
import googlemaps
import google.generativeai as genai
import traceback
import time
from streamlit_local_storage import LocalStorage
import re
import json
from datetime import datetime

# ------------------------------------------------
# APIキー管理（変更なし）
# ------------------------------------------------
def get_user_api_keys():
    localS = LocalStorage()
    maps_key_data = localS.getItem("user_gmaps_api_key")
    gemini_key_data = localS.getItem("user_gemini_api_key")
    maps_key = maps_key_data.get("value") if isinstance(maps_key_data, dict) else maps_key_data
    gemini_key = gemini_key_data.get("value") if isinstance(gemini_key_data, dict) else gemini_key_data
    with st.sidebar:
        st.divider(); st.subheader("🔑 APIキー設定")
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
                        st.success("✅ キーを記憶しました！"); time.sleep(1); st.rerun()
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
# ★★★ これが、新しい、AIへの「最終命令書（プロンプト）」です ★★★
# ------------------------------------------------
def generate_ai_transit_summary(gemini_key, directions_result, origin_query, destination_query):
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        prompt = f"""
        あなたは、ユーザーの隠れた意図を深く理解する、世界最高の旅行コンシェルジュです。
        ユーザーは「{origin_query}」から「{destination_query}」へ移動したいと考えています。
        
        # あなたへの絶対的な命令
        ユーザーの真の目的は、**「電車での乗り換え案内」を知ること**です。
        たとえ、提供された以下のJSONデータが「徒歩」ルートのみを提案していたとしても、それはGoogle Maps APIの仕様上の限界に過ぎません。
        あなたは、そのデータを鵜呑みにしてはいけません。
        
        あなたの使命は、提供されたJSONデータを**「電車での移動を前提として」**解釈し直し、最も自然で、最もユーザーの目的に沿った、最高の乗り換え案内を生成することです。

        # 乗り換え案内 生成ルール
        1.  JSONデータの中に、`"travel_mode": "TRANSIT"` というステップが**含まれている場合**：
            - そのデータを忠実に使い、総所要時間、運賃（あれば）、そして各ステップ（路線名、出発・到着駅、駅数など）を、絵文字を使い、Markdown形式で美しく、詳細に説明してください。
        
        2.  JSONデータの中に、`"travel_mode": "TRANSIT"` というステップが**一切含まれていない場合**（徒歩ルートしか提案されなかった場合）：
            - **絶対に、徒歩ルートをそのまま案内してはいけません。**
            - 代わりに、以下のような、共感的で、誠実な、謝罪と代替案を提示してください。
            - 「申し訳ございません。ご指定の区間は、物理的に距離が非常に近いため、Googleのシステムが徒歩での移動を最適と判断してしまいました。正確な『電車』での乗り換え情報を提供することができませんでした。」
            - 「お手数ですが、より長距離の駅（例：大阪駅から東京駅）でお試しいただくか、Googleマップ公式アプリで、出発時刻を指定して、再度検索していただけますでしょうか。」
            - このように、システムの限界を正直に認め、ユーザーに次のアクションを促す、誠実な対応をしてください。

        3.  常に、プロのコンシェルジュとして、非常に丁寧で、思いやりのある口調を維持してください。

        # Google Maps APIのJSONデータ
        ```json
        {json.dumps(directions_result, ensure_ascii=False, indent=2)}
        ```
        """
        
        response = model.generate_content(prompt)
        return response.text, None
    except Exception as e:
        return None, f"AIによる要約生成中にエラーが発生しました: {e}"

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
            
            with st.spinner("🤖 2人のAIアシスタントが、最終結論を導き出しています..."):
                try:
                    gmaps = googlemaps.Client(key=maps_key)
                    origin_place, origin_error = find_best_place(gmaps, origin_query)
                    if origin_error: st.error(f"出発地エラー: {origin_error}"); return
                    destination_place, dest_error = find_best_place(gmaps, destination_query)
                    if dest_error: st.error(f"目的地エラー: {dest_error}"); return
                    origin_address = origin_place['formatted_address']
                    destination_address = destination_place['formatted_address']
                    
                    directions_result = gmaps.directions(origin=origin_address, destination=destination_address, mode="transit", language="ja", departure_time=datetime.now())
                    
                    if not directions_result:
                        st.error("❌ 指定された場所間のルートが見つかりませんでした。"); return

                    # ★★★ 最後の審判：結果を、AIに委ねる ★★★
                    summary, error = generate_ai_transit_summary(gemini_key, directions_result, origin_query, destination_query)
                    
                    if error:
                        st.error(error)
                    else:
                        st.success("✅ AIコンシェルジュからのご案内です。")
                        st.markdown(summary)

                except Exception as e:
                    st.error("⚠️ 処理中に予期しないエラーが発生しました。")
                    st.code(traceback.format_exc())
    else:
        st.info("👆 サイドバーで、ご自身のAPIキーを設定してください。")
