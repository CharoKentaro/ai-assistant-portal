streamlit.errors.StreamlitDuplicateElementKey: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).

Traceback:
File "/mount/src/ai-assistant-portal/app.py", line 44, in <module>
    localS.setItem("speech_api_key", speech_api_key)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit_local_storage/__init__.py", line 99, in setItem
    _st_local_storage(method="setItem", itemKey=itemKey, itemValue=itemValue, key=key)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/components/v1/custom_component.py", line 59, in __call__
    return self.create_instance(
           ~~~~~~~~~~~~~~~~~~~~^
        *args,
        ^^^^^^
    ...<4 lines>...
        **kwargs,
        ^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/metrics_util.py", line 443, in wrapped_func
    result = non_optional_func(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/components/v1/custom_component.py", line 241, in create_instance
    return_value = marshall_component(dg, element)
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/components/v1/custom_component.py", line 204, in marshall_component
    computed_id = compute_and_register_element_id(
        "component_instance",
    ...<3 lines>...
        url=self.url,
    )
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/lib/utils.py", line 254, in compute_and_register_element_id
    _register_element_id(ctx, element_type, element_id)
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/lib/utils.py", line 143, in _register_element_id
    raise StreamlitDuplicateElementKey(user_key)
