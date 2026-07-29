# 🔥 YouTube 视频排行榜

搜尋任意 YouTube 關鍵詞，生成 **最多觀看 / 最多點讚 / 最多評論 / 互動率最高 / 上升最快** 五個維度的排行榜。

## 部署到 Cloudflare Pages

1. Fork 或 push 此倉庫到 GitHub
2. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com/)
3. 進入 **Workers & Pages** → **Pages** → **連接到 Git**
4. 選擇此倉庫
5. 構建設定：
   - **構建命令**: 留空（純靜態 + Functions）
   - **構建輸出目錄**: 留空
   - **Functions**: 預設即可
6. 點 **保存並部署**

## 在 Cloudflare Pages 設定 API Key

部署完成後：

1. 進入 Pages 專案 → **Settings** → **Functions** → **環境變數**
2. 添加：
   - `YOUTUBE_API_KEY` = 你的 API Key（如果不想讓用戶手動輸入）
3. 部署後，用戶也可以在前端直接輸入自己的 API Key

## 本地開發

直接打開 `index.html` 即可（後端 API 走 Cloudflare Functions）。

## 專案結構

```
youtube-crawler/
├── index.html            # 前端頁面
├── functions/
│   └── api/
│       └── search.js     # API 後端（Cloudflare Pages Functions）
└── .gitignore
```
# Youtube_Crawler
