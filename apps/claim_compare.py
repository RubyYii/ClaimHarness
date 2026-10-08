"""Standalone local ClaimHarness review UI; ProblemBridge is not a prerequisite."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from claim_harness.continuity_ui import available_runs, render_review_tools


st.set_page_config(page_title="ClaimHarness · Compare", layout="wide")
language = st.radio("Language / 语言", ["中文", "English"], horizontal=True)
text = lambda en, zh: zh if language == "中文" else en
st.title(text("ClaimHarness · Review changes", "ClaimHarness · 复查变化"))
st.caption(text("Local source review and saved-audit comparison. Nothing is sent automatically.", "在本地对照原文与已保存的核查结果，不自动发送任何内容。"))
root = Path(st.text_input(text("Folder containing saved audit runs", "保存核查运行的目录"), value="outputs"))
try:
    runs = available_runs(root)
    if runs:
        selected = st.selectbox(text("Saved audit to inspect", "要查看的核查"), list(runs), index=len(runs) - 1)
        def run_action(label, action):
            try:
                with st.spinner(label):
                    return action()
            except (ValueError, RuntimeError, OSError) as exc:
                st.error(str(exc))
        render_review_tools(root, runs[selected].path, text, run_action, standalone=True)
    else:
        st.info(text("Choose a folder containing run_manifest.json in its run subfolders.", "请选择包含核查子目录的文件夹，每个运行中应有 run_manifest.json。"))
except (OSError, ValueError, RuntimeError) as exc:
    st.error(str(exc))
