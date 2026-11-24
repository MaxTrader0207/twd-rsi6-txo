"""外部資料抓取：Yahoo（美元/台幣）、證交所（加權指數）、期交所（TXO 行情、最後結算價）。"""
import re
import time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

import requests

from config import UA, YAHOO_URL, TWSE_TAIEX_URL, TAIFEX_OPT_URL, TAIFEX_FSP_URL

S = requests.Session()
S.headers.update(UA)


def _get(url, retries=3):
    for i in range(retries):
        try:
            r = S.get(url, timeout=60)
            r.raise_for_status()
            return r
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def _post(url, data, retries=3):
    for i in range(retries):
        try:
            r = S.post(url, data=data, timeout=60)
            r.raise_for_status()
            return r
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


# ---------- Yahoo Finance：USD/TWD 日線 ----------
def yahoo_twd_daily(start_ts=1420070400):
    """回傳 [(YYYY-MM-DD, close)]。日期以 (timestamp + 12h) 的 UTC 日期為準（避免英國夏令時間錯位）。"""
    end_ts = int(time.time()) + 86400 * 2
    r = _get(f"{YAHOO_URL}?period1={start_ts}&period2={end_ts}&interval=1d")
    res = r.json()["chart"]["result"][0]
    closes = res["indicators"]["quote"][0]["close"]
    out = []
    for t, c in zip(res["timestamp"], closes):
        if c is None:
            continue
        d = datetime.fromtimestamp(t + 43200, tz=timezone.utc).strftime("%Y-%m-%d")
        if out and out[-1][0] == d:
            out[-1] = (d, c)
        else:
            out.append((d, c))
    return out


# ---------- 證交所：加權指數每日 OHLC ----------
def _num(s):
    return float(str(s).replace(",", ""))


def taiex_month(y, m):
    """回傳 {YYYY-MM-DD: (open, close)}；該月無資料回傳 {}。"""
    r = _get(f"{TWSE_TAIEX_URL}?date={y}{m:02d}01&response=json")
    j = r.json()
    out = {}
    for row in j.get("data") or []:
        ry, rm, rd = row[0].split("/")
        d = f"{int(ry) + 1911}-{rm}-{rd}"
        out[d] = (_num(row[1]), _num(row[4]))
    return out


def taiex_range(start, end):
    """start/end: YYYY-MM-DD。回傳 {date: (open, close)}。"""
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = {}
    while (y, m) <= (ey, em):
        out.update(taiex_month(y, m))
        time.sleep(2.5)  # 證交所限流
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return {k: v for k, v in out.items() if start <= k <= end}


# ---------- 期交所：TXO 每日行情（一般交易時段） ----------
def taifex_opt_day(date):
    """date: YYYY-MM-DD。回傳一般時段列：[日期,契約,到期月份(週別),履約價,買賣權,開盤價,...]；無資料回傳 []。"""
    d = date.replace("-", "/")
    data = {"down_type": "1", "commodity_id": "TXO", "commodity_id2": "",
            "queryStartDate": d, "queryEndDate": d}
    r = _post(TAIFEX_OPT_URL, data)
    text = r.content.decode("big5", errors="ignore")
    rows = []
    for line in text.strip().splitlines()[1:]:
        c = [x.strip() for x in line.split(",")]
        if len(c) > 17 and c[17] == "一般":
            rows.append(c)
    return rows


# ---------- 期交所：臺指選擇權最後結算價 ----------
class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in = [], None, "", False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._in, self._cell = True, ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row.append(re.sub(r"\s+", "", self._cell))
            self._in = False
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in:
            self._cell += data


def taifex_fsp(year):
    """回傳 {契約代碼: (結算日 YYYY-MM-DD, 最後結算價)}，例如 {'202403W1': ('2024-03-06', 19510.0)}。"""
    data = [("commodityIds", "2"), ("_all", "on"), ("start_year", str(year)), ("start_month", "01"),
            ("end_year", str(year)), ("end_month", "12"), ("button", "送出查詢")]
    r = _post(TAIFEX_FSP_URL, data)
    p = _TableParser()
    p.feed(r.text)
    out = {}
    for c in p.rows:
        if len(c) >= 3 and re.fullmatch(r"\d{4}/\d\d/\d\d", c[0]) and c[2] not in ("", "-"):
            out[c[1]] = (c[0].replace("/", "-"), _num(c[2]))
    return out


def taipei_today():
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")
