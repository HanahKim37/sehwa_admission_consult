from __future__ import annotations
import pandas as pd

def search_college_cases(
    db: dict,
    college: str = "",
    department: str = "",
    admission_name: str = "",
    college_list: list | None = None,
) -> dict:
    susi = db.get("susi", pd.DataFrame()).copy()
    jungsi = db.get("jungsi", pd.DataFrame()).copy()

    def _filter(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        result = df.copy()
        if college_list and "college" in result.columns:
            result = result[result["college"].astype(str).isin(college_list)]
        elif college and "college" in result.columns:
            result = result[result["college"].astype(str).str.contains(college, na=False, regex=False)]
        if department and "department" in result.columns:
            if isinstance(department, list):
                result = result[result["department"].astype(str).isin(department)]
            else:
                result = result[result["department"].astype(str).str.contains(department, na=False, regex=False)]
        if admission_name and "admission_name" in result.columns:
            if isinstance(admission_name, list):
                result = result[result["admission_name"].astype(str).isin(admission_name)]
            else:
                result = result[result["admission_name"].astype(str).str.contains(admission_name, na=False, regex=False)]
        return result

    s = _filter(susi)
    j = _filter(jungsi)
    combined = pd.concat([s.assign(source="수시"), j.assign(source="정시")], ignore_index=True)

    summary = {
        "지원자 수": len(combined),
        "최종 합격자 수": int((combined.get("final_result", pd.Series(dtype=str)).astype(str).str.contains("합", na=False)).sum()) if not combined.empty else 0,
        "등록자 수": int((combined.get("registered", pd.Series(dtype=str)).astype(str).str.contains("등록", na=False)).sum()) if not combined.empty else 0,
    }
    return {"summary": summary, "cases": combined}
