from __future__ import annotations
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