"""後端入口（GitHub Actions 執行）。

python backend/run.py signal    # 每個交易日 08:05（台北）：抓 Yahoo 美元/台幣，算 RSI，產生新訊號（待進場）
python backend/run.py update    # 每個交易日 16:30（台北）：補進場開盤價、到期結算、計算損益
python backend/run.py daily     # signal + update
python backend/run.py backfill  # 從 2021-11-22 全部重算（會覆蓋 trades.json）
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config as C
import sources as src
from contracts import pick, pnl, target_wed
from strategy import compute, trigger_levels

DATA = Path(__file__).resolve().parent.parent / "docs" / "data"
F_TRADES, F_STATUS, F_SERIES = DATA / "trades.json", DATA / "status.json", DATA / "series.json"


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def now_tpe():
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ signal
def run_signal(trades, status):
    today = src.taipei_today()
    bars = [b for b in src.yahoo_twd_daily() if b[0] < today]  # 今天（台北）尚未收完的 K 棒不用
    rows = compute(bars)
    last_scanned = status.get("last_scanned", "2026-11-19")
    known = {t["sig"] for t in trades}
    added = 0
    for r in rows:
        if r["date"] <= last_scanned or r["date"] < C.START or not r["signal"] or r["date"] in known:
            continue
        trades.append(dict(sig=r["date"], typ=r["signal"], rsi=r["rsi"], wk_end=r["wk_end"],
                           wk_rsi=r["wk_rsi"], wk_rsi_prev=r["wk_rsi_prev"], status="pending"))
        added += 1
        log(f"新訊號 {r['date']} {r['signal']} RSI={r['rsi']}")
    last = rows[-1]
    status["last_scanned"] = last["date"]
    st = compute.last_state
    put_lv, call_lv = trigger_levels(st["close"], st["up"], st["dn"])
    status["fx"] = dict(date=last["date"], close=last["close"], raw=last["raw"], rsi=last["rsi"],
                        rsi_prev=rows[-2]["rsi"], signal=last["signal"],
                        put_level=put_lv, call_level=call_lv)
    status["week"] = dict(end=last["wk_end"], rsi=last["wk_rsi"], rsi_prev=last["wk_rsi_prev"], dir=last["wk_dir"])
    save(F_SERIES, dict(
        daily=[[r["date"], r["close"], r["rsi"], r["signal"]] for r in rows[-260:]],
        weekly=sorted({(r["wk_end"], r["wk_rsi"]) for r in rows[-600:] if r["wk_end"]})[-80:],
    ))
    log(f"signal: 資料至 {last['date']}，RSI={last['rsi']}，新增 {added} 筆")


# ------------------------------------------------------------------ update
_fsp_cache = {}


def fsp_of(code):
    y = int(code[:4])
    for yy in (y, y + 1):
        if yy not in _fsp_cache:
            try:
                _fsp_cache[yy] = src.taifex_fsp(yy)
            except Exception as e:  # 尚無資料的年份
                log("FSP 抓取失敗", yy, e)
                _fsp_cache[yy] = {}
        if code in _fsp_cache[yy]:
            return _fsp_cache[yy][code]
    return None


def run_update(trades, status):
    today = src.taipei_today()
    pend = [t for t in trades if t["status"] == "pending"]
    if pend:
        start = min(t["sig"] for t in pend)
        taiex = src.taiex_range(start, today)
        td = sorted(taiex)
        # 對應進場日（訊號日之後第一個台股交易日）
        for t in pend:
            t["_entry"] = next((d for d in td if d > t["sig"]), None)
        # 同一進場日多個訊號 → 只取最新訊號日
        by_e = {}
        for t in pend:
            if t["_entry"]:
                by_e.setdefault(t["_entry"], []).append(t)
        for e, ts in by_e.items():
            ts.sort(key=lambda x: x["sig"])
            for t in ts[:-1]:
                t.update(status="merged", entry=e, note=f"同進場日併入 {ts[-1]['sig']}")
            t = ts[-1]
            rows = src.taifex_opt_day(e)
            if not rows:
                log(f"{e} 期交所尚無資料，保留待進場")
                continue
            s0 = taiex[e][0]
            p = pick(rows, e, s0, t["typ"])
            t.update(entry=e, S0=s0, wed=target_wed(e))
            if p is None:
                t.update(status="skipped", note="找不到對應週三合約或履約價")
            elif p["prem"] is None:
                t.update(status="skipped", code=p["code"], strike=p["strike"], note="開盤無成交")
            else:
                t.update(status="open", code=p["code"], strike=p["strike"], prem=p["prem"], lots=C.LOTS)
                log(f"進場 {e} {t['typ']} {p['code']} {p['strike']:.0f} @ {p['prem']}")
        for t in pend:
            t.pop("_entry", None)

    for t in trades:
        if t["status"] != "open" or t.get("wed", "9999") > today:
            continue
        f = fsp_of(t["code"])
        if not f:
            log(f"{t['code']} 尚無最後結算價")
            continue
        pay, pl = pnl(t["typ"], t["strike"], t["prem"], f[1], t.get("lots", C.LOTS))
        t.update(status="settled", fsp=f[1], fsp_date=f[0], payoff=pay, pnl=pl)
        log(f"結算 {t['code']} {t['typ']} {t['strike']:.0f} FSP={f[1]} 損益={pl:,.0f}")


# ------------------------------------------------------------------ main
def main(mode):
    trades = load(F_TRADES, [])
    status = load(F_STATUS, {})
    if mode == "backfill":
        trades, status = [], {"last_scanned": "2021-11-18"}
    if mode in ("signal", "daily", "backfill"):
        run_signal(trades, status)
    if mode in ("update", "daily", "backfill"):
        run_update(trades, status)
    trades.sort(key=lambda t: t["sig"])
    status.update(version=C.VERSION, updated_at=now_tpe(), mode=mode,
                  params=dict(rsi_n=C.RSI_N, up=C.RSI_UP, dn=C.RSI_DN, lots=C.LOTS, slip=C.SLIP,
                              fee=C.FEE, tax=C.TAX, mult=C.MULT, start=C.START),
                  counts={s: sum(t["status"] == s for t in trades)
                          for s in ("pending", "open", "settled", "skipped", "merged")})
    save(F_TRADES, trades)
    save(F_STATUS, status)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "daily")
