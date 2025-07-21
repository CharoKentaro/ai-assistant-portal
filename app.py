# ===============================================================
# 4. UI描画 + ツール起動ロジック（修正版）
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    if "google_user_info" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        flow = get_google_auth_flow()
        authorization_url, state = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes='true')
        st.session_state["google_auth_state"] = state
        st.link_button("🗝️ Googleアカウントでログイン", authorization_url, use_container_width=True)
    else:
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): google_logout()
        st.divider()

        tool_options = ("📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
        
        # 初期化処理を改善
        if 'previous_tool_choice' not in st.session_state:
            st.session_state.previous_tool_choice = None
        if 'sidebar_close_triggered' not in st.session_state:
            st.session_state.sidebar_close_triggered = False
        
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, key="tool_choice_radio")
        
        # ツール選択の変更を検知 OR 初回ツール選択時にサイドバーを閉じる
        should_close_sidebar = False
        
        if tool_choice != st.session_state.previous_tool_choice:
            should_close_sidebar = True
            st.session_state.previous_tool_choice = tool_choice
        
        # モバイル環境でのタップ時にも確実に閉じる処理
        if should_close_sidebar or (tool_choice and not st.session_state.sidebar_close_triggered):
            st.session_state.sidebar_close_triggered = True
            
            # より確実で積極的なサイドバー閉じ処理
            components.html(
                """
                <script>
                let closeAttempts = 0;
                const maxAttempts = 50; // 最大試行回数を増加
                
                const closeSidebar = () => {
                    // 複数のセレクターを試行
                    const selectors = [
                        '[data-testid="stSidebarCloseButton"]',
                        '[data-testid="collapsedControl"]',
                        'button[kind="header"][data-testid*="sidebar"]',
                        '.css-1dp5vir button', // Streamlitのサイドバーボタンの可能性
                        '[aria-label*="close"]'
                    ];
                    
                    for (const selector of selectors) {
                        const elements = window.parent.document.querySelectorAll(selector);
                        for (const element of elements) {
                            if (element && element.click) {
                                element.click();
                                console.log('サイドバーを閉じました:', selector);
                                return true;
                            }
                        }
                    }
                    
                    // フォールバック: キーボードイベントでのEscキー送信
                    const escEvent = new KeyboardEvent('keydown', {
                        key: 'Escape',
                        code: 'Escape',
                        keyCode: 27,
                        which: 27,
                        bubbles: true
                    });
                    window.parent.document.dispatchEvent(escEvent);
                    
                    return false;
                };

                // 即座に1回実行
                closeSidebar();
                
                // その後、短い間隔で複数回試行
                const intervalId = setInterval(() => {
                    closeAttempts++;
                    if (closeSidebar() || closeAttempts >= maxAttempts) {
                        clearInterval(intervalId);
                    }
                }, 30); // 30ミリ秒間隔で試行

                // 3秒後に強制終了
                setTimeout(() => {
                    clearInterval(intervalId);
                }, 3000);
                </script>
                """,
                height=0,
            )

        st.divider()
        
        # 以下、APIキー設定部分は変更なし
        localS = LocalStorage()
        saved_keys = localS.getItem("api_keys")
        gemini_default = saved_keys.get('gemini', '') if isinstance(saved_keys, dict) else ""
        speech_default = saved_keys.get('speech', '') if isinstance(saved_keys, dict) else ""
        
        if 'gemini_api_key' not in st.session_state:
            st.session_state.gemini_api_key = gemini_default
        if 'speech_api_key' not in st.session_state:
            st.session_state.speech_api_key = speech_default

        with st.expander("⚙️ APIキーの表示と再設定", expanded=not(st.session_state.gemini_api_key and st.session_state.speech_api_key)):
            with st.form("api_key_form", clear_on_submit=False):
                st.session_state.gemini_api_key = st.text_input("1. Gemini APIキー", type="password", value=st.session_state.gemini_api_key)
                st.session_state.speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", value=st.session_state.speech_api_key)
                
                col1, col2 = st.columns(2)
                with col1:
                    save_button = st.form_submit_button("💾 保存", use_container_width=True)
                with col2:
                    reset_button = st.form_submit_button("🔄 クリア", use_container_width=True)

        if save_button:
            localS.setItem("api_keys", {"gemini": st.session_state.gemini_api_key, "speech": st.session_state.speech_api_key})
            st.success("キーを保存しました！"); time.sleep(1); st.rerun()
        
        if reset_button:
            localS.setItem("api_keys", None); st.session_state.gemini_api_key = ""; st.session_state.speech_api_key = ""
            st.success("キーをクリアしました。"); time.sleep(1); st.rerun()
