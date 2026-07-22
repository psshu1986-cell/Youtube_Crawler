# 🔥 中国神仙视频排行榜 - YouTube 爬虫

搜尋 YouTube 上關於中國神仙、神話、傳說相關影片，生成**最多觀看**和**上升最快**兩個排行榜。

## 功能

- **最多觀看排行** — 關鍵詞搜索，按總觀看數排名
- **上升最快排行** — 搜尋近期發布影片，按日均觀看數（velocity）排名
- **Web 搜尋頁面** — 自訂關鍵詞、時間範圍，直接在瀏覽器操作
- **CSV 匯出** — 排行榜可儲存為 CSV 檔案
- **智慧過濾** — 自動排除 shorts/短影片、美食/旅遊/釣魚/遊戲等無關內容
- **代理支援** — 可配置 HTTP 代理

## 技術棧

- Python 3.12
- Flask（Web 服務）
- YouTube Data API v3
- pandas（數據處理）
- Rich（終端表格展示）

## 快速開始

### 1. 取得 YouTube API Key

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立專案 → 啟用 **YouTube Data API v3**
3. 建立憑證 → **API 金鑰**

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 執行爬蟲（終端模式）

```bash
python crawler.py --api-key 你的API_KEY --proxy http://127.0.0.1:7897
```

參數說明：
| 參數 | 說明 |
|------|------|
| `--api-key` | YouTube Data API Key（必填） |
| `--proxy` | 代理地址，如 `http://127.0.0.1:7897` |
| `--rising-days` | 上升榜統計天數，預設 60 |
| `--max-results` | 每榜顯示條數，預設 15 |
| `--output, -o` | 輸出 CSV 檔案路徑 |

### 4. 啟動 Web 服務

```bash
python app.py --api-key 你的API_KEY --proxy http://127.0.0.1:7897
```

打開瀏覽器訪問 `http://127.0.0.1:5000`

## 專案結構

```
youtube-crawler/
├── app.py             # Flask Web 服務
├── crawler.py         # 終端排行榜工具
├── youtube_api.py     # YouTube API 核心模組
├── templates/
│   └── index.html     # Web 前端頁面
├── requirements.txt   # Python 依賴
├── .env.example       # 環境變數範例
└── .gitignore
```

## 配額說明

YouTube Data API 每日免費配額 **10,000 units**：
- `search.list`：100 units / 次
- `videos.list`：1 unit / 支影片

每次完整執行約耗費 **200–300 units**，每日可跑 **30–50 次**。

## 搜尋關鍵詞

預設搜尋關鍵詞：
- 中国神仙 神话故事
- 封神榜 电影 电视剧
- 山海经 异兽
- 道教神仙 人物
- 民间传说 故事
- 古代神话 中国
- 天庭 众神
- 中国诸神

可在 Web 頁面或程式碼中自訂。
