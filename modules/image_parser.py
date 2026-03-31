from __future__ import annotations
from typing import BinaryIO

def extract_text_from_image(file: BinaryIO) -> str:
    # 1차 버전에서는 이미지 OCR 고도화 전 placeholder
    return ""

def parse_consult_image(text: str) -> dict:
    return {
        "basic": {"student_id": "", "name": "", "track": ""},
        "grades": [],
        "mocks": [],
        "raw_text": text,
    }
