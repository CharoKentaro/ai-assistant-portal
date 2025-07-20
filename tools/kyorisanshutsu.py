# tools/kyorisanshutsu.py

import streamlit as st
import googlemaps
import traceback

def show_tool():
    """距離算出ツールを表示・実行する関数"""

    st.header("📍 距離算出ツール")
    st.info("出発地と目的地の住所を入力すると、実際の移動距離と所要時間を計算します。")
    st.markdown("---")

    # ------------------------------------------------
    # 1. APIキーをSecretsから安全に取得
    # ------------------------------------------------
    try:
        gmaps_api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("🚨 重大なエラー：StreamlitのSecretsに`GOOGLE_MAPS_API_KEY`が設定されていません。")
        st.warning("このツールを利用するには、管理者によるAPIキーの設定が必要です。")
        # APIキーがなければ、ここで処理を終了
        return

    # ------------------------------------------------
    # 2. ユーザーからの入力
    # ------------------------------------------------
    with st.form("distance_form"):
        origin = st.text_input("出発地の住所", placeholder="例：東京駅")
        destination = st.text_input("目的地の住所", placeholder="例：大阪駅")
        submit_button = st.form_submit_button(label="🚗 距離と時間を計算する")

    # ------------------------------------------------
    # 3. 計算ボタンが押された後の処理
    # ------------------------------------------------
    if submit_button:
        if not origin or not destination:
            st.warning("出発地と目的地の両方を入力してください。")
        else:
            with st.spinner(f"「{origin}」から「{destination}」へのルートを検索中..."):
                try:
                    # Google Maps Clientを初期化
                    gmaps = googlemaps.Client(key=gmaps_api_key)

                    # directions APIを呼び出し（'driving'は自動車でのルート）
                    directions_result = gmaps.directions(origin,
                                                         destination,
                                                         mode="driving")
                    
                    # 結果が存在するかチェック
                    if directions_result:
                        # 最初のルート情報（最も一般的なルート）を取得
                        leg = directions_result[0]['legs'][0]
                        distance = leg['distance']['text']
                        duration = leg['duration']['text']
                        
                        st.success("✅ ルートが見つかりました！")
                        
                        col1, col2 = st.columns(2)
                        col1.metric("総移動距離", distance)
                        col2.metric("予想所要時間", duration)
                        
                        # 生のレスポンスを見たい場合（デバッグ用）
                        with st.expander("詳細なAPIレスポンスを見る"):
                            st.json(directions_result)
                    else:
                        st.error("指定された住所間のルートが見つかりませんでした。住所を確認して再試行してください。")

                except Exception as e:
                    st.error("APIの呼び出し中にエラーが発生しました。")
                    st.error(f"エラー詳細: {e}")
                    st.code(traceback.format_exc())
