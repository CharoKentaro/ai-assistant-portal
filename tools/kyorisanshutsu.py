# tools/kyorisanshutsu.py
import streamlit as st

def show_tool():
    """距離算出ツールを表示・実行する関数"""
    st.header("📍 距離算出ツール")
    st.info("このツールは現在、モジュール化のテスト段階です。")
    st.write("ここに、距離を算出するための具体的な機能（入力欄や計算ロジック）を実装していきます。")
    
    # 例として入力欄を設置
    address1 = st.text_input("出発地の住所")
    address2 = st.text_input("目的地の住所")

    if st.button("距離を計算する"):
        if address1 and address2:
            st.success(f"「{address1}」から「{address2}」までの距離を計算します。（計算機能は今後実装）")
        else:
            st.warning("出発地と目的地の両方を入力してください。")
