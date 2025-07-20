# tools/koutsuhi.py (AI搭載の最終完成版 - APIキー削除バグ修正済み)

import streamlit as st
import googlemaps
import traceback
import time
from streamlit_local_storage import LocalStorage

# ------------------------------------------------
# APIキーを管理する心臓部
# ------------------------------------------------
def get_user_api_key():
    """
    ユーザーのブラウザにAPIキーを保存・管理し、そのキーを返す関数。
    """
    localS = LocalStorage()
    saved_key_data = localS.getItem("user_gmaps_api_key")
    
    with st.sidebar:
        st.divider()
        st.subheader("🔑 APIキー設定 (AI乗り換え案内)")
        
        key_value = None
        # パターン①：データが「辞書」形式で、中に'value'キーがある
        if isinstance(saved_key_data, dict) and saved_key_data.get("value"):
            key_value = saved_key_data["value"]
        # パターン②：データが「文字列」として直接保存されている
        elif isinstance(saved_key_data, str) and saved_key_data:
            key_value = saved_key_data

        # 有効なキーが見つかった場合
        if key_value:
            st.success("✅ APIキーは設定済みです。")
            
            # APIキーの一部を表示（セキュリティのため最初の数文字のみ）
            masked_key = key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "設定済み"
            st.caption(f"現在のキー: {masked_key}")
            
            if st.button("🔄 APIキーを変更・削除する"):
                # ★★★ 修正ポイント：完全にキーを削除する ★★★
                try:
                    localS.deleteItem("user_gmaps_api_key")  # deleteItemを使用
                except:
                    # deleteItemが使えない場合の代替手段
                    try:
                        localS.removeItem("user_gmaps_api_key")  # removeItemを試す
                    except:
                        # 最終手段：空の値を設定
                        localS.setItem("user_gmaps_api_key", "")
                
                st.success("🗑️ APIキーを削除しました。ページを更新します...")
                time.sleep(1)
                st.rerun()
            return key_value

        # 有効なキーが見つからなかった場合
        else:
            st.warning("⚠️ Google Maps APIキーが設定されていません。")
            with st.form("api_key_form"):
                st.info("💡 下の入力欄にご自身のAPIキーを入力してください。キーは、あなたのブラウザ内にのみ安全に保存されます。")
                new_key = st.text_input(
                    "あなたのGoogle Maps APIキー", 
                    type="password",
                    help="AIzaSy... で始まる文字列を入力してください"
                )
                submitted = st.form_submit_button("🔐 このAPIキーをブラウザに記憶させる")
                
                if submitted:
                    if not new_key or len(new_key.strip()) < 20:
                        st.error("❌ 有効なAPIキーを入力してください。")
                    else:
                        # 辞書形式で保存
                        localS.setItem("user_gmaps_api_key", {"value": new_key.strip()})
                        st.success("✅ キーを記憶しました！ページを更新します...")
                        time.sleep(1)
                        st.rerun()
            
            return None

# ------------------------------------------------
# 駅名を自動的に拡張・補完する関数
# ------------------------------------------------
def expand_station_name(address):
    """駅名を自動的に拡張・補完する"""
    if not address:
        return address
    
    # 一般的な駅名の略称辞書（関西圏を中心に）
    station_expansions = {
        # 大阪・関西圏（近鉄沿線）
        "小阪": "河内小阪駅",
        "八戸ノ里": "八戸ノ里駅", 
        "布施": "布施駅",
        "鶴橋": "鶴橋駅",
        "今里": "今里駅",
        "新深江": "新深江駅",
        "小路": "小路駅",
        "若江岩田": "若江岩田駅",
        "河内花園": "河内花園駅",
        "東花園": "東花園駅",
        "瓢箪山": "瓢箪山駅",
        "枚岡": "枚岡駅",
        "額田": "額田駅",
        "石切": "石切駅",
        "生駒": "生駒駅",
        
        # 大阪市内主要駅
        "大阪": "大阪駅",
        "梅田": "梅田駅",
        "天王寺": "天王寺駅",
        "難波": "難波駅",
        "なんば": "難波駅",
        "心斎橋": "心斎橋駅",
        "本町": "本町駅",
        "淀屋橋": "淀屋橋駅",
        "京橋": "京橋駅",
        "新大阪": "新大阪駅",
        "西九条": "西九条駅",
        "弁天町": "弁天町駅",
        
        # 関西その他主要駅
        "京都": "京都駅",
        "神戸": "神戸駅",
        "三宮": "三宮駅",
        "奈良": "奈良駅",
        "和歌山": "和歌山駅",
        
        # 東京圏主要駅
        "東京": "東京駅",
        "新宿": "新宿駅",
        "渋谷": "渋谷駅",
        "池袋": "池袋駅",
        "品川": "品川駅",
        "上野": "上野駅",
        "秋葉原": "秋葉原駅",
        "有楽町": "有楽町駅",
        "銀座": "銀座駅",
        "六本木": "六本木駅",
        
        # その他全国主要駅
        "名古屋": "名古屋駅",
        "博多": "博多駅",
        "札幌": "札幌駅",
        "仙台": "仙台駅",
        "広島": "広島駅",
        "福岡": "博多駅",
    }
    
    address_clean = address.strip()
    
    # 既に「駅」が含まれている場合はそのまま
    if "駅" in address or "station" in address.lower():
        return address
    
    # 略称辞書で完全一致を探す
    if address_clean in station_expansions:
        return station_expansions[address_clean]
    
    # 部分一致も試す
    for short_name, full_name in station_expansions.items():
        if short_name in address_clean:
            return address.replace(short_name, full_name)
    
    # 日本語で終わる場合は「駅」を追加
    import re
    if re.search(r'[ひ-ゟヲ-ヿ一-鿿]$', address_clean):
        return f"{address_clean}駅"
    
    return address

# ------------------------------------------------
# 曖昧な地名をGoogle Places APIで特定する関数
# ------------------------------------------------
def find_best_place(gmaps, query):
    """Google Places APIを使って曖昧な地名から最適な場所を特定"""
    if not query: 
        return None, "入力が空です。"
    
    try:
        # まず駅名を拡張
        expanded_query = expand_station_name(query)
        
        # Places APIで検索
        places_result = gmaps.places(
            query=expanded_query, 
            language="ja", 
            region="JP",
            type="establishment"  # より具体的な場所を優先
        )
        
        if places_result and places_result.get("status") == "OK" and places_result.get("results"):
            best_place = places_result["results"][0]
            return best_place, None
        else:
            # Places APIで見つからない場合、Geocoding APIを試す
            try:
                geocode_result = gmaps.geocode(expanded_query, region="JP", language="ja")
                if geocode_result:
                    # Geocoding結果をPlaces API形式に変換
                    place_info = {
                        'formatted_address': geocode_result[0]['formatted_address'],
                        'geometry': geocode_result[0]['geometry'],
                        'name': expanded_query
                    }
                    return place_info, None
            except:
                pass
                
            return None, f"「{query}」に一致する場所が見つかりませんでした。"
            
    except Exception as e:
        return None, f"場所の検索中にエラーが発生しました: {e}"

# ------------------------------------------------
# ツールの本体
# ------------------------------------------------
def show_tool():
    """AI乗り換え案内（交通費計算）ツールを表示・実行するメイン関数"""

    st.header("🚇 AI乗り換え案内")
    
    user_api_key = get_user_api_key()
    
    if user_api_key:
        st.info("🤖 出発地と目的地の駅名や住所を、自由に入力してください。AIが最適な場所を推測します。")
        
        # 使用例を表示
        with st.expander("💡 使い方とコツ"):
            st.markdown("""
            **このツールは以下のような入力に対応しています：**
            
            ✅ **駅名（略称でもOK）：**
            - 小阪 → 河内小阪駅
            - 布施 → 布施駅
            - 大阪 → 大阪駅
            - 東京 → 東京駅
            
            ✅ **観光地・施設名：**
            - USJ、大阪城公園、東京タワー
            - イオンモール、阪急百貨店
            
            ✅ **住所：**
            - 大阪府東大阪市小阪1-1-1
            - 東京都渋谷区渋谷1-1-1
            
            **💡 AIが自動で最適な場所を見つけます！**
            """)
        
        st.markdown("---")

        with st.form("distance_form"):
            origin_query = st.text_input(
                "🚩 出発地", 
                placeholder="例：小阪、新宿、大阪城公園、USJ",
                help="駅名、住所、施設名など何でもOK！"
            )
            destination_query = st.text_input(
                "🎯 目的地", 
                placeholder="例：布施、東京駅、ディズニーランド",
                help="AIが最適な場所を自動で見つけます"
            )
            
            # 移動手段の選択
            transport_mode = st.selectbox(
                "🚗 移動手段",
                options=["driving", "walking", "transit", "bicycling"],
                format_func=lambda x: {
                    "driving": "🚗 車",
                    "walking": "🚶 徒歩", 
                    "transit": "🚇 公共交通機関",
                    "bicycling": "🚲 自転車"
                }[x],
                index=0
            )
            
            submit_button = st.form_submit_button(label="🔍 ルートを検索する")

        if submit_button:
            if not origin_query or not destination_query:
                st.warning("⚠️ 出発地と目的地の両方を入力してください。")
            else:
                with st.spinner("🤖 AIが最適なルートを検索中..."):
                    try:
                        gmaps = googlemaps.Client(key=user_api_key)
                        
                        # 出発地を特定
                        origin_place, origin_error = find_best_place(gmaps, origin_query)
                        if origin_error: 
                            st.error(f"❌ 出発地の検索エラー: {origin_error}")
                            return

                        # 目的地を特定
                        destination_place, dest_error = find_best_place(gmaps, destination_query)
                        if dest_error: 
                            st.error(f"❌ 目的地の検索エラー: {dest_error}")
                            return
                        
                        # 特定された場所を表示
                        origin_address = origin_place['formatted_address']
                        destination_address = destination_place['formatted_address']
                        
                        st.success("🎯 場所を特定しました！")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"🚩 **出発地**\n{origin_address}")
                        with col2:
                            st.info(f"🎯 **目的地**\n{destination_address}")

                        # ルート検索を実行
                        directions_result = gmaps.directions(
                            origin=origin_address, 
                            destination=destination_address, 
                            mode=transport_mode, 
                            language="ja",
                            region="JP"
                        )
                        
                        if directions_result:
                            route = directions_result[0]
                            leg = route['legs'][0]
                            
                            st.success("✅ ルートが見つかりました！")
                            
                            # メイン情報を表示
                            col1, col2 = st.columns(2)
                            col1.metric("📏 総移動距離", leg['distance']['text'])
                            col2.metric("⏱️ 予想所要時間", leg['duration']['text'])
                            
                            # 追加情報
                            with st.expander("📋 詳細情報"):
                                st.write(f"**開始地点:** {leg['start_address']}")
                                st.write(f"**終了地点:** {leg['end_address']}")
                                
                                # ステップごとの案内（簡略版）
                                if 'steps' in leg:
                                    st.write("**主要な経路:**")
                                    for i, step in enumerate(leg['steps'][:5]):  # 最初の5ステップのみ
                                        # HTMLタグを除去
                                        import re
                                        clean_instruction = re.sub('<.*?>', '', step['html_instructions'])
                                        st.write(f"{i+1}. {clean_instruction} ({step['distance']['text']})")
                                    
                                    if len(leg['steps']) > 5:
                                        st.write("... (他の経路は省略)")
                            
                        else:
                            st.error("❌ 指定された場所間のルートが見つかりませんでした。")
                            st.info("💡 別の移動手段を試してみるか、より具体的な住所を入力してください。")
                            
                    except googlemaps.exceptions.ApiError as api_error:
                        error_message = str(api_error)
                        st.error("🚫 APIの呼び出し中にエラーが発生しました。")
                        
                        if "NOT_FOUND" in error_message:
                            st.error("❌ 住所が見つかりませんでした。")
                        elif "API key not valid" in error_message or "INVALID_REQUEST" in error_message:
                            st.error("🔑 APIキーが正しくないようです。サイドバーからキーを再設定してください。")
                        elif "OVER_QUERY_LIMIT" in error_message:
                            st.error("📊 APIの利用制限に達しました。しばらく時間をおいてから再度お試しください。")
                        else:
                            st.error(f"エラー詳細: {api_error}")
                            
                    except Exception as e:
                        st.error("⚠️ 予期しないエラーが発生しました。")
                        st.error(f"エラー詳細: {e}")
                        with st.expander("🔧 デバッグ情報"):
                            st.code(traceback.format_exc())
                        
    else:
        # APIキーがまだ設定されていない場合の案内
        st.info("👆 サイドバーで、ご自身のGoogle Maps APIキーを設定してください。")
        with st.expander("🔑 APIキーと、必要なAPIについて"):
            st.markdown("""
            ### 必要なGoogle Maps APIキー
            
            このツールを使用するには、以下のAPIが有効なGoogle Maps APIキーが必要です：
            
            ✅ **必要なAPI:**
            - Google Maps Directions API
            - Google Maps Places API
            - Google Maps Geocoding API
            
            ### 取得方法:
            1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
            2. プロジェクトを作成
            3. 「API とサービス」→「認証情報」でAPIキーを作成
            4. 上記のAPIを有効化
            
            ### セキュリティ:
            - 入力したAPIキーはあなたのブラウザにのみ保存されます
            - 開発者や第三者には見えません
            - いつでも削除・変更が可能です
            """)
