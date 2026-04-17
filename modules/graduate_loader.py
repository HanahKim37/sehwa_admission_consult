from __future__ import annotations
from io import BytesIO
from typing import BinaryIO
import pandas as pd

REQUIRED_SHEETS = ["내신성적", "모의고사", "수시상담용", "정시상담용"]
OPTIONAL_SHEETS = ["명부", "출력양식(수시)", "출력양식(정시)"]


def _read_sheet(file: BinaryIO, sheet_name: str) -> pd.DataFrame:
    """
    내신성적/모의고사는 다중 헤더 시트이므로 별도 처리.
    """
    if sheet_name == "내신성적":
        return pd.read_excel(file, sheet_name=sheet_name, header=[0, 1, 2])
    if sheet_name == "모의고사":
        return pd.read_excel(file, sheet_name=sheet_name, header=[0, 1])
    return pd.read_excel(file, sheet_name=sheet_name)


def load_excel_file(file: BinaryIO) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(file)
    workbook = {}

    for sheet in xls.sheet_names:
        file.seek(0)
        try:
            workbook[sheet] = _read_sheet(file, sheet)
        except Exception:
            file.seek(0)
            workbook[sheet] = pd.read_excel(file, sheet_name=sheet, header=None)

    return workbook


def detect_required_sheets(workbook_dict: dict[str, pd.DataFrame]) -> dict[str, str]:
    result = {}
    keys = set(workbook_dict.keys())
    for sheet in REQUIRED_SHEETS:
        result[sheet] = "정상" if sheet in keys else "누락"
    for sheet in OPTIONAL_SHEETS:
        result[sheet] = "참고용 인식" if sheet in keys else "없음"
    return result


def summarize_workbook(workbook_dict: dict[str, pd.DataFrame]) -> dict[str, int]:
    summary = {}
    for name, df in workbook_dict.items():
        summary[name] = len(df)
    return summary


def load_from_google_drive() -> dict[str, pd.DataFrame]:
    """Streamlit Secrets의 서비스 계정으로 Google Drive에서 기본 졸업생 엑셀을 로드합니다."""
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    service = build("drive", "v3", credentials=credentials)
    file_id = st.secrets["GRAD_FILE_ID"]

    request = service.files().get_media(fileId=file_id)
    buffer = BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return load_excel_file(buffer)