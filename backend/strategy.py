"""v1.0 訊號邏輯（純計算，不連網）。

Buy Put ：日線 RSI(6) > 80，且上一個完整週（週一～週五）的週線 RSI(6) 比再前一週高（上揚）
Buy Call：日線 RSI(6) < 20，且上一個完整週的週線 RSI(6) 比再前一週低（下彎）
"""
from datetime import date, timedelta

from config import RSI_N, RSI_UP, RSI_DN, BAD_TICK


def clean(closes, thr=BAD_TICK):
    """錯價過濾：與前後各 2 根（不含自己）的中位數差距 > thr 時，以中位數取代。"""
    out = list(closes)
    n = len(closes)
    for i in range(n):
        nb = sorted(closes[k] for k in range(max(0, i - 2), min(n, i + 3)) if k != i)
        if not nb:
            continue
        m = nb[len(nb) // 2] if len(nb) % 2 else (nb[len(nb) // 2 - 1] + nb[len(nb) // 2]) / 2
        if abs(closes[i] / m - 1) > thr:
            out[i] = m
    return out


def rsi_wilder(a, n=RSI_N, state=None):
    """三竹 RSI：前 n 期簡單平均起算，之後 UP = UP + (U − UP)/n。state（dict）會寫入最後的 up/dn。"""
    o = [None] * len(a)
    up = dn = 0.0
    for i in range(1, len(a)):
        ch = a[i] - a[i - 1]
        u, d = max(ch, 0.0), max(-ch, 0.0)
        if i <= n:
            up += u / n
            dn += d / n
            if i == n:
                o[i] = 100 * up / (up + dn) if up + dn else 50.0
        else:
            up += (u - up) / n
            dn += (d - dn) / n
            o[i] = 100 * up / (up + dn) if up + dn else 50.0
    if state is not None:
        state.update(up=up, dn=dn)
    return o


def trigger_levels(last_close, up, dn, n=RSI_N, hi=RSI_UP, lo=RSI_DN):
    """下一根日線收盤要到多少，RSI 才會 > hi 或 < lo。回傳 (put_level, call_level)。"""
    r_hi, r_lo = hi / (100 - hi), lo / (100 - lo)          # up/dn 比值門檻：80→4、20→0.25
    need_up = (n - 1) * (r_hi * dn - up)                    # 上漲點數 ch > need_up
    need_dn = (n - 1) * (up / r_lo - dn) if r_lo else None  # 下跌點數 > need_dn
    put = last_close + max(need_up, 0.0)
    call = last_close - max(need_dn, 0.0)
    return round(put, 4), round(call, 4)


def week_key(d):
    x = date.fromisoformat(d)
    return (x - timedelta(days=x.weekday())).isoformat()  # 該週週一


def compute(bars):
    """bars: [(date, close)] 依日期排序。回傳每日 dict：date, close, rsi, wk_end, wk_rsi, wk_rsi_prev, wk_dir, signal。"""
    dates = [d for d, _ in bars]
    x = clean([c for _, c in bars])
    st = {}
    rsi = rsi_wilder(x, state=st)
    compute.last_state = dict(st, close=x[-1]) if x else {}

    wk_keys, wk_close, wk_last_date, widx = [], [], [], []
    for d, c in zip(dates, x):
        k = week_key(d)
        if not wk_keys or wk_keys[-1] != k:
            wk_keys.append(k)
            wk_close.append(c)
            wk_last_date.append(d)
        else:
            wk_close[-1] = c
            wk_last_date[-1] = d
        widx.append(len(wk_keys) - 1)
    wrsi = rsi_wilder(wk_close)

    out = []
    for i, d in enumerate(dates):
        w = widx[i]
        a = wrsi[w - 1] if w >= 1 else None   # 上一個完整週
        b = wrsi[w - 2] if w >= 2 else None   # 再前一週
        wdir = None
        if a is not None and b is not None:
            wdir = "up" if a > b else "down" if a < b else "flat"
        sig = None
        if rsi[i] is not None and wdir:
            if rsi[i] > RSI_UP and wdir == "up":
                sig = "P"
            elif rsi[i] < RSI_DN and wdir == "down":
                sig = "C"
        out.append(dict(date=d, close=round(x[i], 4), raw=bars[i][1], rsi=None if rsi[i] is None else round(rsi[i], 2),
                        wk_end=wk_last_date[w - 1] if w >= 1 else None,
                        wk_rsi=None if a is None else round(a, 2),
                        wk_rsi_prev=None if b is None else round(b, 2),
                        wk_dir=wdir, signal=sig))
    return out
