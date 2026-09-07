import io
import math
import re
from datetime import datetime, date, timedelta
import pandas as pd

TOTAL_RE = re.compile(r"^\s*(grand\s+)?(total|sub\s*-?\s*total|summary|closing)\b", re.I)
NUM_CLEAN_RE = re.compile(r"[^\d.\-]")
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d/%m/%y",
                "%Y/%m/%d", "%m/%d/%Y", "%d %B %Y", "%b %d, %Y", "%Y%m%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%b-%Y %H:%M"]


def _cell(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d") if (v.hour == 0 and v.minute == 0) else v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        s = v.strip()
        return s or None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if hasattr(v, "item"):
        return v.item()
    return v


def parse_file(filename: str, data: bytes):
    ext = filename.lower().rsplit(".", 1)[-1]
    frames = []
    if ext == "csv":
        text = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(io.StringIO(text), header=None, dtype=object, skip_blank_lines=False, engine="python",
                         on_bad_lines="skip")
        frames.append(("Sheet1", df))
    elif ext in ("xlsx", "xlsm", "xls"):
        engine = "xlrd" if ext == "xls" else "openpyxl"
        for name, df in pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=object, engine=engine).items():
            frames.append((str(name), df))
    else:
        raise ValueError(f"Unsupported file type .{ext}")
    sheets = []
    for name, df in frames:
        rows = [[_cell(v) for v in row] for row in df.itertuples(index=False, name=None)]
        sheets.append({"name": name, "rows": rows, "n_rows": len(rows), "n_cols": int(df.shape[1]) if len(df.shape) > 1 else 0})
    return sheets


def detect_header_row(rows, known_norms: set, normalize):
    best = (None, -1.0, 0)
    for i, row in enumerate(rows[:40]):
        cells = [c for c in row if c is not None]
        if len(cells) < 3:
            continue
        strs = [c for c in cells if isinstance(c, str)]
        str_ratio = len(strs) / len(cells)
        if str_ratio < 0.6:
            continue
        hits = sum(1 for c in strs if normalize(c) in known_norms)
        score = hits * 3 + str_ratio * 2 + min(len(cells), 12) / 12
        if i + 1 < len(rows) and sum(1 for c in rows[i + 1] if c is not None) < 2:
            score -= 1.5
        if score > best[1]:
            best = (i, score, hits)
    if best[0] is None:
        return 0, 20
    ncols = len([c for c in rows[best[0]] if c is not None])
    conf = min(100, 45 + int(55 * best[2] / max(ncols, 1))) if best[2] else 45
    return best[0], conf


def extract_rows(rows, header_idx):
    hdr = rows[header_idx] if header_idx < len(rows) else []
    headers, seen = [], {}
    for i, h in enumerate(hdr):
        name = str(h).strip() if h is not None else f"Column {i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        headers.append(name)
    data, skipped_blank, skipped_total = [], 0, 0
    for offset, r in enumerate(rows[header_idx + 1:]):
        vals = [c for c in r if c is not None]
        if not vals:
            skipped_blank += 1
            continue
        first = vals[0]
        is_total = (isinstance(first, str) and TOTAL_RE.match(first)) or (
            len(vals) <= max(2, len(headers) // 2) and any(isinstance(c, str) and TOTAL_RE.match(c) for c in vals))
        if is_total:
            skipped_total += 1
            continue
        rec = {headers[i]: (r[i] if i < len(r) else None) for i in range(len(headers))}
        rec["__source_row"] = header_idx + offset + 2
        data.append(rec)
    return headers, data, {"blank": skipped_blank, "totals": skipped_total}


def parse_number(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = NUM_CLEAN_RE.sub("", s.replace(",", ""))
    if s in ("", "-", "."):
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def parse_date(v):
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 < v < 80000:
            return (datetime(1899, 12, 30) + timedelta(days=int(v))).strftime("%Y-%m-%d")
        s = str(int(v))
    else:
        s = str(v).strip()
    if not s:
        return None
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def infer_type(samples):
    vals = [s for s in samples if s is not None]
    if not vals:
        return "empty"
    dates = sum(1 for s in vals if parse_date(s) is not None and not (isinstance(s, (int, float)) and s < 20000))
    nums = sum(1 for s in vals if parse_number(s) is not None and not (isinstance(s, str) and re.search(r"[/\-][A-Za-z0-9]", s) and parse_date(s)))
    n = len(vals)
    if dates / n >= 0.7 and any(isinstance(s, str) and re.search(r"[-/. ]", s) for s in vals):
        return "date"
    if nums / n >= 0.8:
        return "number"
    if dates / n >= 0.7:
        return "date"
    return "string"
