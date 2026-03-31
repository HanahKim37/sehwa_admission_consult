from __future__ import annotations
import streamlit as st
import pandas as pd

def render_header_box(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div style="padding:14px 16px;border-radius:14px;background:#F4F7FB;border:1px solid #D9E2F1;">
            <div style="font-weight:700;font-size:1.05rem;margin-bottom:6px;">{title}</div>
            <div style="color:#374151;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_status_badge(status: str) -> None:
    color_map = {
        "정상": "#D1FAE5",
        "일부 누락": "#FEF3C7",
        "확인 필요": "#FEE2E2",
        "누락": "#FEE2E2",
    }
    text_map = {
        "정상": "#065F46",
        "일부 누락": "#92400E",
        "확인 필요": "#991B1B",
        "누락": "#991B1B",
    }
    bg = color_map.get(status, "#E5E7EB")
    fg = text_map.get(status, "#374151")
    st.markdown(
        f"""<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{bg};color:{fg};font-size:0.85rem;font-weight:600;">{status}</span>""",
        unsafe_allow_html=True,
    )

def render_summary_card(title: str, value: str, help_text: str | None = None) -> None:
    extra = f'<div style="font-size:0.82rem;color:#6B7280;margin-top:6px;">{help_text}</div>' if help_text else ""
    st.markdown(
        f"""
        <div style="padding:16px;border-radius:16px;border:1px solid #E5E7EB;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <div style="font-size:0.9rem;color:#6B7280;">{title}</div>
            <div style="font-size:1.35rem;font-weight:700;margin-top:4px;">{value}</div>
            {extra}
        </div>
        """,
        unsafe_allow_html=True,
    )

def styled_dataframe(df: pd.DataFrame, use_container_width: bool = True) -> None:
    st.dataframe(df, use_container_width=use_container_width)
