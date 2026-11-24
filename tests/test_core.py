"""離線測試：python -m pytest tests -q"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from contracts import code_expiry, target_wed, pick, pnl  # noqa: E402
from strategy import clean, rsi_wilder, trigger_levels, compute  # noqa: E402


def test_expiry_codes():
    assert code_expiry("202403W1") == "2024-03-06"
    assert code_expiry("202403") == "2024-03-20"
    assert code_expiry("202603F1") is None
    assert target_wed("2024-03-04") == "2024-03-06"   # 週一 → 本週三
    assert target_wed("2024-03-06") == "2024-03-13"   # 週三 → 下週三


def test_pick_otm1():
    def row(code, k, cp, o):
        return ["2024/03/04", "TXO", code, f"{k}.0000", cp, o] + ["-"] * 11 + ["一般"]
    rows = [row("202403W1", k, cp, str(k % 1000)) for k in range(19300, 19800, 50) for cp in ("買權", "賣權")]
    rows += [row("202403", 19500, "買權", "999")]
    p = pick(rows, "2024-03-04", 19512, "P")
    assert p["code"] == "202403W1" and p["strike"] == 19450
    c = pick(rows, "2024-03-04", 19512, "C")
    assert c["strike"] == 19550


def test_pnl_matches_backtest():
    trades = json.loads((ROOT / "docs/data/trades.json").read_text(encoding="utf-8"))
    for t in trades:
        _, pl = pnl(t["typ"], t["strike"], t["prem"], t["fsp"], t["lots"])
        assert abs(pl - t["pnl"]) < 0.01
    assert round(sum(t["pnl"] for t in trades)) == 1487807


def test_clean_bad_tick():
    x = [30.0, 30.1, 30.05, 3.01, 30.2, 30.1, 30.0]
    assert abs(clean(x)[3] - 30.1) < 0.2


def test_trigger_levels():
    import random
    random.seed(1)
    a = [30 + random.uniform(-0.1, 0.1) for _ in range(60)]
    st = {}
    rsi_wilder(a, state=st)
    put_lv, call_lv = trigger_levels(a[-1], st["up"], st["dn"])
    assert rsi_wilder(a + [put_lv + 1e-6])[-1] > 80 - 1e-6
    assert rsi_wilder(a + [put_lv - 0.01])[-1] < 80 or put_lv == a[-1]
    assert rsi_wilder(a + [call_lv - 1e-6])[-1] < 20 + 1e-6


def test_compute_signal_needs_weekly_dir():
    # 連續上漲：日線 RSI > 80，週線也上揚 → Put
    from datetime import date, timedelta
    d0 = date(2024, 1, 1)
    bars, v = [], 30.0
    for i in range(120):
        d = d0 + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        v *= 1.001
        bars.append((d.isoformat(), v))
    out = compute(bars)
    assert out[-1]["rsi"] > 80 and out[-1]["wk_dir"] in ("up", "flat")
