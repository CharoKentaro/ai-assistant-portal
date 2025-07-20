import streamlit as st
import google.generativeai as genai
import json
import pandas as pd

# ===============================================================
# 専門家のメインの仕事 (司令塔 app.py から呼び出される)
# ===============================================================

def show_tool(gemini_api_key):
    """価格リサーチツールのUIと機能をすべてここに集約"""
    st.header("💹 万能！価格リサーチツール")
    st.info("調べたいもののキーワードを入力すると、AIが関連商品の価格情報をリサーチし、スプレッドシート用のファイル（CSV）を作成します。")

    keyword = st.text_input("リサーチしたいキーワードを入力してください（例：20代向け メンズ香水, 北海道の人気お土産）")

    if st.button("このキーワードで価格情報をリサーチする"):
        if not gemini_api_key:
            st.error("サイドバーでGemini APIキーを設定してください。")
        elif not keyword:
            st.warning("キーワードを入力してください。")
        else:
            with st.spinner(f"AIが「{keyword}」の価格情報をリサーチしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    
                    # 「成功コード」の魂である、洗練されたシステムプロンプト
                    system_prompt = f"""
                    あなたは、ユーザーから指定されたキーワードに基づいて、関連商品のリストと、その平均的な価格を調査する、非常に優秀なリサーチアシスタントです。
                    ユーザーからのキーワードは「{keyword}」です。
                    このキーワードに関連する商品やサービスの情報を、20個、リストアップしてください。
                    情報は、必ず以下のJSON形式の配列のみで回答してください。他の言葉は一切含めないでください。
                    - 「name」には、商品名やサービス名を具体的に記入してください。
                    - 「price」には、日本円での平均的な販売価格を、必ず数値のみで記入してください。不明な場合は0と記入してください。
                    ```json
                    [
                      {{ "name": "（商品名1）", "price": (価格1) }},
                      {{ "name": "（商品名2）", "price": (価格2) }}
                    ]
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content(f"「{keyword}」に関連する商品・サービスの価格情報を20個教えてください。")
                    
                    # AIの応答からJSON部分を安全に抽出
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    item_list = json.loads(json_text)
                    
                    if not item_list:
                        st.warning("情報を取得できませんでした。キーワードを変えてお試しください。")
                    else:
                        # pandasを使ってデータを整形・表示
                        df = pd.DataFrame(item_list)
                        df.columns = ["項目名", "価格（円）"]
                        df['価格（円）'] = pd.to_numeric(df['価格（円）'], errors='coerce')
                        df_sorted = df.sort_values(by="価格（円）", na_position='last')

                        st.success(f"「{keyword}」のリサーチが完了しました！")
                        
                        # CSVダウンロードボタン
                        csv_data = df_sorted.to_csv(index=False, encoding='utf_8_sig').encode('utf_8_sig')
                        st.download_button(
                            label=f"「{keyword}」の価格リストをダウンロード (.csv)",
                            data=csv_data,
                            file_name=f"{keyword}_research.csv",
                            mime="text/csv"
                        )
                        st.dataframe(df_sorted)

                except Exception as e:
                    st.error(f"リサーチ中にエラーが発生しました: {e}")
