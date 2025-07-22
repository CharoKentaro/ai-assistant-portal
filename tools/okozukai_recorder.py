# tools/okozukai_recorder.py

import streamlit as st
import google.generativeai as genai
from streamlit_local_storage import LocalStorage
import json
from PIL import Image
import io
import time
import pandas as pd
from datetime import datetime

# --- このツール専用のプロンプト ---
GEMINI_PROMPT = """
あなたは、レシートの画像を直接解析する、超優秀な経理アシスタントAIです。
# 指示
レシートの画像の中から、以下の情報を注意深く、正確に抽出してください。
1.  **合計金額 (total_amount)**: 支払いの総額。
2.  **購入品リスト (items)**: 購入した「品物名(name)」と「その単価(price)」のリスト。
# 出力形式
*   抽出した結果を、必ず以下のJSON形式で出力してください。
*   数値は、数字のみを抽出してください（円やカンマは不要）。
*   値が見つからない場合は、数値項目は "0"、リスト項目は空のリスト `[]` としてください。
*   「小計」「お預り」「お釣り」「店名」「合計」といった単語そのものは、購入品リストに含めないでください。
*   JSON以外の、前置きや説明は、絶対に出力しないでください。
{
  "total_amount": "ここに合計金額の数値",
  "items": [
    { "name": "ここに品物名1", "price": "ここに単価1" },
    { "name": "ここに品物名2", "price": "ここに単価2" }
  ]
}
"""

# --- このツール専用の関数 ---
def calculate_remaining_balance(monthly_allowance, total_spent):
    return monthly_allowance - total_spent

def format_balance_display(balance):
    if balance >= 0:
        return f"🟢 **{balance:,.0f} 円**"
    else:
        return f"🔴 **{abs(balance):,.0f} 円 (予算オーバー)**"


# --- ポータルから呼び出されるメイン関数 ---
def show_tool(gemini_api_key):
    st.header("💰 お小遣いレコーダー", divider='rainbow')

    # --- ローカルストレージの準備 ---
    try:
        localS = LocalStorage()
    except Exception as e:
        st.error(f"🚨 重大なエラー：ローカルストレージの初期化に失敗しました。エラー詳細: {e}")
        st.stop()

    # --- セッションステートの初期化 ---
    # ツールごとにユニークなキーを接頭辞として使い、他のツールとの衝突を避ける
    prefix = "okozukai_"
    if f"{prefix}initialized" not in st.session_state:
        st.session_state[f"{prefix}monthly_allowance"] = float(localS.getItem("okozukai_monthly_allowance") or 0.0)
        st.session_state[f"{prefix}total_spent"] = float(localS.getItem("okozukai_total_spent") or 0.0)
        st.session_state[f"{prefix}receipt_preview"] = None
        st.session_state[f"{prefix}all_receipts"] = localS.getItem("okozukai_all_receipt_data") or []
        st.session_state[f"{prefix}initialized"] = True

    # --- 確認モードの処理 ---
    if st.session_state[f"{prefix}receipt_preview"]:
        st.subheader("📝 支出の確認")
        st.info("AIが読み取った内容を確認・修正し、問題なければ「確定」してください。")

        preview_data = st.session_state[f"{prefix}receipt_preview"]

        corrected_amount = st.number_input(
            "AIが読み取った合計金額はこちらです。必要なら修正してください。",
            value=preview_data['total_amount'], min_value=0.0, step=1.0, key=f"{prefix}correction_input"
        )

        st.write("📋 **品目リスト（直接編集できます）**")
        if preview_data['items']:
            df_items = pd.DataFrame(preview_data['items'])
            df_items['price'] = pd.to_numeric(df_items['price'], errors='coerce').fillna(0)
        else:
            df_items = pd.DataFrame([{"name": "", "price": 0}])
            st.info("AIは品目を検出できませんでした。手動で追加・修正してください。")

        edited_df = st.data_editor(
            df_items, num_rows="dynamic",
            column_config={
                "name": st.column_config.TextColumn("品物名", required=True, width="large"),
                "price": st.column_config.NumberColumn("金額（円）", format="%d円", required=True),
            },
            key=f"{prefix}data_editor", use_container_width=True
        )
        
        st.divider()
        st.write("📊 **支出後の残高プレビュー**")
        current_allowance = st.session_state[f"{prefix}monthly_allowance"]
        current_spent = st.session_state[f"{prefix}total_spent"]
        projected_spent = current_spent + corrected_amount
        projected_balance = calculate_remaining_balance(current_allowance, projected_spent)

        col1, col2, col3 = st.columns(3)
        col1.metric("今月の予算", f"{current_allowance:,.0f} 円")
        col2.metric("使った金額", f"{projected_spent:,.0f} 円", delta=f"+{corrected_amount:,.0f} 円", delta_color="inverse")
        col3.metric("残り予算", f"{projected_balance:,.0f} 円", delta=f"-{corrected_amount:,.0f} 円", delta_color="inverse")

        st.divider()
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("💰 この金額で支出を確定する", type="primary", use_container_width=True):
            new_receipt_record = {
                "date": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "total_amount": corrected_amount,
                "items": edited_df.to_dict('records')
            }
            st.session_state[f"{prefix}all_receipts"].append(new_receipt_record)
            localS.setItem("okozukai_all_receipt_data", st.session_state[f"{prefix}all_receipts"])

            st.session_state[f"{prefix}total_spent"] += corrected_amount
            localS.setItem("okozukai_total_spent", st.session_state[f"{prefix}total_spent"])

            st.session_state[f"{prefix}receipt_preview"] = None
            st.success(f"🎉 {corrected_amount:,.0f} 円の支出を記録しました！")
            st.balloons()
            time.sleep(2)
            st.rerun()
        if cancel_col.button("❌ キャンセル", use_container_width=True):
            st.session_state[f"{prefix}receipt_preview"] = None
            st.rerun()

    # --- 通常モードの処理 ---
    else:
        st.info("レシートを登録して、今月使えるお金を管理しよう！")

        with st.expander("💳 今月のお小遣い設定", expanded=(st.session_state[f"{prefix}monthly_allowance"] == 0)):
             with st.form(key=f"{prefix}allowance_form"):
                new_allowance = st.number_input(
                    "今月のお小遣いを入力してください",
                    value=st.session_state[f"{prefix}monthly_allowance"], step=1000.0, min_value=0.0
                )
                if st.form_submit_button("この金額で設定する", use_container_width=True):
                    st.session_state[f"{prefix}monthly_allowance"] = new_allowance
                    localS.setItem("okozukai_monthly_allowance", new_allowance)
                    st.success(f"今月のお小遣いを {new_allowance:,.0f} 円に設定しました！")
                    time.sleep(1)
                    st.rerun()
        
        st.divider()
        st.subheader("📊 現在の状況")
        current_allowance = st.session_state[f"{prefix}monthly_allowance"]
        current_spent = st.session_state[f"{prefix}total_spent"]
        remaining_balance = calculate_remaining_balance(current_allowance, current_spent)
        col1, col2, col3 = st.columns(3)
        col1.metric("今月の予算", f"{current_allowance:,.0f} 円")
        col2.metric("使った金額", f"{current_spent:,.0f} 円")
        col3.metric("残り予算", f"{remaining_balance:,.0f} 円")
        
        st.markdown(f"#### 🎯 今使えるお金は…")
        st.markdown(f"<p style='text-align: center; font-size: 2.5em; font-weight: bold;'>{format_balance_display(remaining_balance)}</p>", unsafe_allow_html=True)
        if current_allowance > 0:
            progress_ratio = min(current_spent / current_allowance, 1.0)
            st.progress(progress_ratio)
            st.caption(f"予算使用率: {progress_ratio * 100:.1f}%")
        
        st.divider()
        st.subheader("📸 レシートを登録する")
        st.write("##### 方法１：カメラで直接撮影する")
        camera_image = st.camera_input("📷 カメラを起動", help="スマホのカメラでレシートを直接撮影します。")
        st.write("##### 方法２：保存済みの画像を選ぶ")
        file_uploader = st.file_uploader("📁 画像をアップロード", type=['png', 'jpg', 'jpeg'], help="撮影済みのレシート画像をファイルから選択します。")
        uploaded_file = camera_image or file_uploader

        if uploaded_file:
            st.image(uploaded_file, caption="解析対象のレシート", width=300)
            if st.button("⬆️ このレシートを解析する", use_container_width=True, type="primary"):
                if not gemini_api_key:
                    st.warning("サイドバーからGemini APIキーを設定してください。")
                else:
                    try:
                        with st.spinner("🧠 AIがレシートを解析中..."):
                            genai.configure(api_key=gemini_api_key)
                            model = genai.GenerativeModel('gemini-1.5-flash-latest')
                            image = Image.open(uploaded_file)
                            gemini_response = model.generate_content([GEMINI_PROMPT, image])
                            cleaned_text = gemini_response.text.strip().replace("```json", "```").replace("```", "")
                            extracted_data = json.loads(cleaned_text)

                        st.session_state[f"{prefix}receipt_preview"] = {
                            "total_amount": float(extracted_data.get("total_amount", 0)),
                            "items": extracted_data.get("items", [])
                        }
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 解析エラー: {e}")
                        if 'gemini_response' in locals(): st.code(gemini_response.text, language="text")
        
        st.divider()
        st.subheader("🗂️ データ管理")
        if st.session_state[f"{prefix}all_receipts"]:
            st.info(f"現在、{len(st.session_state[f'{prefix}all_receipts'])} 件のレシートデータが保存されています。")
            flat_list_for_csv = []
            for receipt in st.session_state[f'{prefix}all_receipts']:
                items = receipt.get('items');
                if not items: continue
                for item in items:
                    flat_list_for_csv.append({ "日付": receipt.get('date', 'N/A'), "品物名": item.get('name', 'N/A'), "金額": item.get('price', 0), "レシート合計": receipt.get('total_amount', 0) })
            
            if flat_list_for_csv:
                df_for_csv = pd.DataFrame(flat_list_for_csv)
                st.download_button(label="✅ 全支出履歴をCSVでダウンロード", data=df_for_csv.to_csv(index=False, encoding='utf-8-sig'), file_name=f"okozukai_history_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        
        c1, c2 = st.columns(2)
        if c1.button("支出履歴のみリセット", use_container_width=True):
            st.session_state[f"{prefix}total_spent"] = 0.0
            st.session_state[f"{prefix}all_receipts"] = []
            localS.setItem("okozukai_total_spent", 0.0)
            localS.setItem("okozukai_all_receipt_data", [])
            st.success("支出履歴をリセットしました！"); time.sleep(1); st.rerun()
        if c2.button("⚠️ 全データ完全初期化", use_container_width=True, help="予算設定も含め、このツールの全データを消去します。"):
            localS.setItem("okozukai_monthly_allowance", 0.0)
            localS.setItem("okozukai_total_spent", 0.0)
            localS.setItem("okozukai_all_receipt_data", [])
            #セッションステートもクリア
            for key in list(st.session_state.keys()):
                if key.startswith(prefix):
                    del st.session_state[key]
            st.success("全データをリセットしました！"); time.sleep(1); st.rerun()
