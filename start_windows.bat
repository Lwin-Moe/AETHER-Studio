@echo off
REM AETHER UI နှင့် background worker ကို Windows terminal နှစ်ခုဖြင့်စတင်ရန်
start "AETHER Worker" cmd /k python worker.py
start "AETHER UI" cmd /k streamlit run app.py
