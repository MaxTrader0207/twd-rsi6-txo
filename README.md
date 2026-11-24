# 台幣 RSI(6) × TXO 週選買方｜v1.0 凍結版

前後端分離：

| 層 | 位置 | 做什麼 |
|---|---|---|
| 後端 | `backend/`＋GitHub Actions | 抓 Yahoo 美元/台幣、證交所加權指數、期交所 TXO 行情與最後結算價；算訊號、進場、結算、損益，寫入 `docs/data/*.json` |
| 前端 | `docs/`＋GitHub Pages | 純靜態頁，只讀 JSON 顯示：今日訊號、觸發價、持倉、累積損益、RSI 圖、年度統計、交易明細 |

## 規則（v1.0，參數在 `backend/config.py`，改了就是新版本）

- 訊號：Yahoo `TWD=X` 日線，錯價過濾後算 RSI(6)（三竹／威爾德平滑）
- Buy Put：日線 RSI > 80 且上一個完整週的週線 RSI(6) 上揚
- Buy Call：日線 RSI < 20 且上一個完整週的週線 RSI(6) 下彎
- 進場：訊號日後第一個台股交易日，TXO 一般時段開盤價；同一進場日多個訊號只取最新
- 合約：進場日後最近的週三到期（W 或月選），進場日是週三則用下週三；不用 F 系列
- 履約價：加權開盤價找價平，取價外一檔；開盤無成交不進場
- 出場：持有到結算（期交所最後結算價）
- 每筆 2 口；滑價 4 點/口；手續費單邊 NT$35（歸零不收平倉費）；期交稅 0.1%

## 排程（`.github/workflows/daily.yml`，週一～五）

| 台北時間 | 模式 | 內容 |
|---|---|---|
| 08:05 | `daily` | 用前一日完整日 K 算訊號 → 新增「待進場」；順便處理可結算的部位 |
| 16:40 | `update` | 補今日進場的合約、履約價、開盤權利金；週三後補結算價與損益 |
| 19:40 | `update` | 期交所資料延遲時重試 |

> 訊號一定要用台北早上 08:00 左右的 Yahoo 資料（前一日完整日 K）。回測顯示改用央行 16:00 收盤價會失去優勢。

GitHub cron 可能延遲 5～30 分鐘；開盤前要下單的話，08:05 的排程通常 08:30 前會跑完。

## 部署

1. 在 GitHub 建立 repo（例如 `MaxTrader0207/twd-rsi6-txo`），把這個資料夾推上去。
2. Settings → Pages → Source 選 **Deploy from a branch**，Branch `main`、資料夾 `/docs`。
3. Settings → Actions → General → Workflow permissions 選 **Read and write permissions**。
4. Actions → daily → Run workflow，mode 填 `daily` 跑第一次。

`docs/data/trades.json` 已預載回測的 129 筆（+NT$1,487,807），第一次執行會從 2026-11-20 的訊號接著跑。
若要整段重算驗證，手動執行 mode=`backfill`（約 5～10 分鐘，會覆蓋 trades.json）。

## 本機

```bash
pip install -r requirements.txt pytest
python -m pytest tests -q          # 離線測試（成本模型逐筆比對回測 129 筆）
python backend/run.py daily        # 需能連到 Yahoo／證交所／期交所
cd docs && python -m http.server   # 開 http://localhost:8000
```

## 資料檔（`docs/data/`）

- `status.json`：最新匯率、日線 RSI、上週週線方向、今日訊號、次日觸發收盤價、各狀態筆數
- `trades.json`：每筆訊號的生命週期 `pending → open → settled`（或 `skipped` 開盤無成交、`merged` 同進場日併入）
- `series.json`：近 260 日日線 RSI、近 80 週週線 RSI（畫圖用）
