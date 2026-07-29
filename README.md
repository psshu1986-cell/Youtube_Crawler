# 🔥 YouTube 视频排行榜爬虫

搜尋任意 YouTube 關鍵詞，生成 **最多觀看 / 最多點讚 / 最多評論 / 互動率最高 / 上升最快** 五個維度的排行榜。

## 功能

- **五維排行榜** — 最多觀看、最多點讚、最多評論、互動率最高、上升最快
- **關鍵詞自由輸入** — 用空格或逗號分隔多個關鍵詞
- **Web 搜尋頁面** — 直接在瀏覽器操作，五個 Tab 切換
- **CSV 匯出** — 一鍵下載排行榜
- **代理支援** — 可配置 HTTP 代理

## 一鍵部署到 Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. 點擊上方按鈕 → 連接 GitHub 倉庫
2. 設定環境變數：
   - `YOUTUBE_API_KEY`：你的 YouTube Data API Key
   - `PROXY_URL`：代理地址（如 `http://代理IP:端口`）
3. 部署完成後即可訪問

## 本地開發

```bash
pip install -r requirements.txt
python app.py --api-key 你的KEY --proxy http://127.0.0.1:7897
```

打開瀏覽器訪問 `http://127.0.0.1:10000`

## 技術棧

- Python 3.12 + Flask
- YouTube Data API v3
- pandas
