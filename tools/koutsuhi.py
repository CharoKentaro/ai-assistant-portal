import streamlit as st
import google.generativeai as genai
import traceback
import json

# ===============================================================
# 専門家のメインの仕事
# ===============================================================
def show_tool(gemini_api_key): # 司令塔から、Gemini APIキーを、受け取るように、近代化改修します
    
    # この専門家は、もはや、APIキーの管理について、一切、知りません。
    # サイドバーに、何かを描画する、という、越権行為も、一切、行いません。

    st.info("出発地と目的地を入力すると、AIが標準的な所要時間や料金に基づいた最適なルートを3つ提案します。")
    st.warning("※これはリアルタイムの運行情報を反映したものではありません。あくまで目安としてご利用ください。")
    
    col1, col2 = st.columns(2)
    with col1:
        start_station = st.text_input("🚩 出発地を入力してください", "大阪")
    with col2:
        end_station = st.text_input("🎯 目的地を入力してください", "小阪")

    if st.button(f"「{start_station}」から「{end_station}」へのルートを検索"):
        # 司令塔から渡された、APIキーの存在を、ここで、初めて、チェックします
        if not gemini_api_key:
            st.error("サイドバーでGemini APIキーを設定してください。")
        else:
            with st.spinner(f"AIが「{start_station}」から「{end_station}」への最適なルートをシミュレーションしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    
                    system_prompt = """
                    あなたは、日本の公共交通機関の膨大なデータベースを内蔵した、世界最高の「乗り換え案内エンジン」です。
                    ユーザーから指定された「出発地」と「目的地」に基づき、標準的な所要時間、料金、乗り換え情報を基に、最適な移動ルートをシミュレートするのがあなたの役割です。
                    1. **3つのルート提案:** 必ず、「早さ・安さ・楽さ」のバランスが良い、優れたルートを「3つ」提案してください。
                    2. **厳格なJSONフォーマット:** 出力は、必ず、以下のJSON形式の配列のみで回答してください。他の言葉、説明、言い訳は、一切含めないでください。
                    3. **経路の詳細 (steps):** `transport_type`, `line_name`, `station_from`, `station_to`, `details` を記述してください。
                    4. **サマリー情報:** `total_time`, `total_fare`, `transfers` を数値のみで記述してください。
                    ```json
                    [
                      {
                        "route_name": "ルート1：最速",
                        "summary": { "total_time": 30, "total_fare": 450, "transfers": 1 },
                        "steps": [
                          { "transport_type": "電車", "line_name": "JR大阪環状線", "station_from": "大阪", "station_to": "鶴橋", "details": "内回り" },
                          { "transport_type": "徒歩", "details": "近鉄線へ乗り換え" },
                          { "transport_type": "電車", "line_name": "近鉄奈良線", "station_from": "鶴橋", "station_to": "河内小阪", "details": "普通・奈良行き" }
                        ]
                      },
                      { "route_name": "ルート2：乗り換え楽", "summary": { "total_time": 35, "total_fare": 480, "transfers": 0 }, "steps": [] },
                      { "route_name": "ルート3：最安", "summary": { "total_time": 40, "total_fare": 400, "transfers": 2 }, "steps": [] }
                    ]
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content(f"出発地：{start_station}, 目的地：{end_station}")
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    routes = json.loads(json_text)
                    
                    st.success(f"AIによるルートシミュレーションが完了しました！")
                    
                    for i, route in enumerate(routes):
                        with st.expander(f"**{route.get('route_name', 'ルート')}** - 約{route.get('summary', {}).get('total_time', '?')}分 / {route.get('summary', {}).get('total_fare', '?')}円 / 乗り換え{route.get('summary', {}).get('transfers', '?')}回", expanded=(i==0)):
                            if route.get('steps'):
                                for step in route['steps']:
                                    if step.get('transport_type') == "電車":
                                        st.markdown(f"**<font color='blue'>{step.get('station_from', '?')}</font>**", unsafe_allow_html=True)
                                        st.markdown(f"｜ 🚃 {step.get('line_name', '不明な路線')} ({step.get('details', '')})")
                                    elif step.get('transport_type') == "徒歩":
                                        st.markdown(f"**<font color='green'>👟 {step.get('details', '徒歩')}</font>**", unsafe_allow_html=True)
                                    elif step.get('transport_type') == "バス":
                                        st.markdown(f"**<font color='purple'>{step.get('station_from', '?')}</font>**", unsafe_allow_html=True)
                                        st.markdown(f"｜ 🚌 {step.get('line_name', '不明なバス')} ({step.get('details', '')})")
                            st.markdown(f"**<font color='red'>{end_station}</font>**", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"シミュレーション中にエラーが発生しました: {e}")
                    st.code(traceback.format_exc())
