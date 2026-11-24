"""TXO 合約與履約價選擇、損益計算（純計算）。"""
import re
from datetime import date, timedelta

from config import LOTS, MULT, SLIP, FEE, TAX


def nth_wed(y, m, n):
    d = date(y, m, 1)
    d += timedelta(days=(2 - d.weekday()) % 7)
    return (d + timedelta(weeks=n - 1)).isoformat()


def code_expiry(code):
    """'202403W1' → 第 1 個週三；'202403' → 第 3 個週三（月選）；F 系列（週五到期）→ None。"""
    if "F" in code or not re.fullmatch(r"\d{6}(W\d)?", code):
        return None
    y, m = int(code[:4]), int(code[4:6])
    w = re.search(r"W(\d)", code)
    return nth_wed(y, m, int(w.group(1)) if w else 3)


def target_wed(entry):
    """進場日之後最近的週三；進場日即週三則用下週三。"""
    d = date.fromisoformat(entry)
    k = (2 - d.weekday()) % 7 or 7
    return (d + timedelta(days=k)).isoformat()


def pick(rows, entry, s0, typ):
    """rows：期交所一般時段列。回傳 dict(code, wed, strike, prem) 或 None（找不到合約）。prem 為 None 表示開盤無成交。"""
    wed = target_wed(entry)
    codes = sorted({r[2] for r in rows if code_expiry(r[2]) == wed})
    if not codes:
        return None
    code = codes[0]
    cp = "賣權" if typ == "P" else "買權"
    rr = [r for r in rows if r[2] == code and r[4] == cp]
    ks = sorted({float(r[3]) for r in rr})
    if not ks:
        return None
    ai = min(range(len(ks)), key=lambda i: (abs(ks[i] - s0), i))
    j = ai - 1 if typ == "P" else ai + 1
    if j < 0 or j >= len(ks):
        return None
    k = ks[j]
    row = next(r for r in rr if float(r[3]) == k)
    prem = None if row[5] in ("-", "") else float(row[5])
    return dict(code=code, wed=wed, strike=k, prem=prem)


def pnl(typ, strike, prem, fsp, lots=LOTS):
    """回傳 (到期價值點數, 總損益 NT$)。滑價 4 點/口、手續費單邊 35、稅 0.1%。"""
    paid = prem + SLIP
    pay = max(strike - fsp, 0.0) if typ == "P" else max(fsp - strike, 0.0)
    per = (pay - paid) * MULT - (FEE + paid * MULT * TAX) - ((FEE + pay * MULT * TAX) if pay > 0 else 0.0)
    return pay, round(per * lots, 2)
