"""v1.0 凍結版參數 — 請勿任意修改，修改即為新版本。"""
VERSION = "v1.0"

# 訊號
RSI_N = 6            # RSI(6)，三竹 / Wilder 平滑
RSI_UP = 80          # 日線 RSI > 80 → Buy Put
RSI_DN = 20          # 日線 RSI < 20 → Buy Call
BAD_TICK = 0.01      # 與前後各 2 根中位數差距 > 1% 視為錯價，以中位數取代

# 部位與成本
LOTS = 2             # 每筆固定 2 口
MULT = 50            # TXO 每點 NT$50
SLIP = 4             # 滑價 4 點 / 口（進場）
FEE = 35             # 手續費每口單邊 NT$35（到期歸零不計平倉費）
TAX = 0.001          # 期交稅 0.1%（權利金與結算價值）

# 回測起點
START = "2021-11-22"

# 資料來源
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/TWD=X"
TWSE_TAIEX_URL = "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST"
TAIFEX_OPT_URL = "https://www.taifex.com.tw/cht/3/dlOptDataDown"
TAIFEX_FSP_URL = "https://www.taifex.com.tw/cht/5/optIndxFSP"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
