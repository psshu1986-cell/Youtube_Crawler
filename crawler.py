"""
YouTube 中国神仙视频排行榜爬虫

用法：
  python crawler.py --api-key YOUR_KEY
  python crawler.py --api-key YOUR_KEY --rising-days 30 --max-results 20

如需存成 CSV：
  python crawler.py --api-key YOUR_KEY --output ranking.csv

使用代理：
  python crawler.py --api-key YOUR_KEY --proxy http://127.0.0.1:7897
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from rich.console import Console
from rich.table import Table

# ── 中国神仙相关搜索关键词 ──────────────────────────────────
SEARCH_KEYWORDS = [
    "中国神仙 神话故事",
    "中国神话 传说",
    "封神榜 电影 电视剧",
    "山海经 异兽",
    "中国神话故事 动画",
    "道教神仙 人物",
    "民间传说 故事",
    "古代神话 中国",
    "天庭 众神",
    "中国诸神",
]

# 排除关键词（避免无关内容：美食/景区/运动/音乐/钓鱼/游戏等）
EXCLUDE_KEYWORDS = [
    "游戏", "攻略", "MMO", "手游", "cosplay", "搞笑",
    "神仙豆腐", "神仙居", "神仙球", "神仙翻唱", "神仙水",
    "美食", "菜谱", "景区", "旅游", "羽毛球",
    "钓鱼", "钓法", "鱼饵",
    "翻唱", "cover", "弹唱",
    "shorts", "#shorts",
]

TZ = timezone.utc

# Windows GBK 相容設定
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
console = Console(force_terminal=True) if sys.platform == "win32" else Console()

# YouTube API 基础地址
YT_API = "https://www.googleapis.com/youtube/v3"


# ═══════════════════════════════════════════════════════════════
#  API 调用（直接 requests，不依赖 google-api-python-client）
# ═══════════════════════════════════════════════════════════════

def get_session(proxy: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
        # 超时设长一点，走代理可能慢
        session.timeout = 30
    return session


def api_get(session: requests.Session, path: str, params: dict) -> dict | None:
    """请求 YouTube Data API 并返回 JSON。"""
    url = f"{YT_API}/{path}"
    try:
        resp = session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        console.print(f"[red]请求超时: {url}[/red]")
    except requests.exceptions.ConnectionError as e:
        console.print(f"[red]连接失败 (检查代理/网络): {e}[/red]")
    except requests.exceptions.HTTPError as e:
        console.print(f"[red]API 错误 ({resp.status_code}): {resp.text[:200]}[/red]")
    except Exception as e:
        console.print(f"[red]未知错误: {e}[/red]")
    return None


def search_videos(
    session: requests.Session, api_key: str, query: str,
    order: str = "viewCount", max_results: int = 50,
    published_after: str = None,
) -> list[dict]:
    """调用 search.list，返回视频元数据列表。"""
    params = dict(
        part="snippet",
        q=query,
        type="video",
        order=order,
        maxResults=min(max_results, 50),
        relevanceLanguage="zh",
        videoDuration="long",  # long = >20分钟，过滤 Shorts/短视频
        key=api_key,
    )
    if published_after:
        params["publishedAfter"] = published_after

    data = api_get(session, "search", params)
    if not data:
        return []

    items = data.get("items", [])
    results = []
    for item in items:
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        if any(kw in title for kw in EXCLUDE_KEYWORDS):
            continue
        results.append({
            "videoId": video_id,
            "title": title,
            "channelId": item["snippet"]["channelId"],
            "channelTitle": item["snippet"]["channelTitle"],
            "publishedAt": item["snippet"]["publishedAt"],
            "description": item["snippet"].get("description", "")[:200],
        })
    return results


def get_video_stats(
    session: requests.Session, api_key: str, video_ids: list[str],
    min_duration_sec: int = 300,
) -> dict[str, dict]:
    """批量获取视频统计数据，过滤短于 min_duration_sec 的视频。"""
    stats_map = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        data = api_get(session, "videos", {
            "part": "statistics,contentDetails",
            "id": ",".join(batch),
            "key": api_key,
        })
        if not data:
            continue

        for item in data.get("items", []):
            vid = item["id"]

            # ISO 8601 duration → 秒
            raw_dur = item.get("contentDetails", {}).get("duration", "PT0S")
            dur_sec = iso8601_duration_to_seconds(raw_dur)
            if dur_sec < min_duration_sec:
                continue

            stat = item.get("statistics", {})
            stats_map[vid] = {
                "viewCount": int(stat.get("viewCount", 0)),
                "likeCount": int(stat.get("likeCount", 0)),
                "commentCount": int(stat.get("commentCount", 0)),
            }
    return stats_map


def iso8601_duration_to_seconds(dur: str) -> int:
    """将 PT1H2M3S 转为秒数。"""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not m:
        return 0
    h, m_, s = [int(g) if g else 0 for g in m.groups()]
    return h * 3600 + m_ * 60 + s


# ═══════════════════════════════════════════════════════════════
#  核心逻辑
# ═══════════════════════════════════════════════════════════════

def fetch_all_videos(
    session: requests.Session, api_key: str, keywords: list[str],
    order: str, max_per_keyword: int = 50, published_after: str = None,
) -> pd.DataFrame:
    """多关键词搜索去重，返回 DataFrame。"""
    seen = set()
    rows = []

    for kw in keywords:
        results = search_videos(
            session, api_key, kw, order=order,
            max_results=max_per_keyword, published_after=published_after,
        )
        for r in results:
            if r["videoId"] not in seen:
                seen.add(r["videoId"])
                rows.append(r)
        console.print(f"  [dim]{kw}: {len(results)} 条 (累计 {len(rows)} 条去重)[/dim]")

    if not rows:
        return pd.DataFrame()

    # 批量获取统计信息
    video_ids = [r["videoId"] for r in rows]
    stats = get_video_stats(session, api_key, video_ids)

    # 合并数据
    records = []
    for r in rows:
        s = stats.get(r["videoId"], {})
        if not s:
            continue
        published = datetime.fromisoformat(r["publishedAt"].replace("Z", "+00:00"))
        days_since = max((datetime.now(TZ) - published).total_seconds() / 86400, 0.01)

        records.append({
            "videoId": r["videoId"],
            "title": r["title"],
            "channelTitle": r["channelTitle"],
            "publishedAt": published.strftime("%Y-%m-%d %H:%M"),
            "viewCount": s["viewCount"],
            "likeCount": s["likeCount"],
            "commentCount": s["commentCount"],
            "daysSincePublished": round(days_since, 1),
            "velocity": round(s["viewCount"] / days_since),  # 日均观看
            "url": f"https://youtu.be/{r['videoId']}",
        })

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════
#  展示
# ═══════════════════════════════════════════════════════════════

def print_table(df: pd.DataFrame, title: str, sort_by: str, top_n: int = 20):
    """在终端打印排行榜表格。"""
    df = df.sort_values(sort_by, ascending=False).head(top_n).reset_index(drop=True)

    table = Table(title=f"\n{title}", title_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("标题", width=50)
    table.add_column("频道", width=18)
    table.add_column("发布时间", width=14)
    table.add_column("观看", justify="right", width=10)
    table.add_column("点赞", justify="right", width=8)
    table.add_column("日均观看", justify="right", width=10)

    for i, (_, row) in enumerate(df.iterrows(), 1):
        table.add_row(
            str(i),
            row["title"][:48],
            row["channelTitle"][:16],
            row["publishedAt"],
            format_num(row["viewCount"]),
            format_num(row["likeCount"]),
            format_num(int(row["velocity"])),
        )

    console.print(table)
    return df


def format_num(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}万"
    return str(n)


# ═══════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="YouTube 中国神仙视频排行榜")
    parser.add_argument("--api-key", required=True, help="YouTube Data API Key")
    parser.add_argument("--rising-days", type=int, default=60, help="上升榜统计范围（天）")
    parser.add_argument("--max-results", type=int, default=15, help="每榜展示条数")
    parser.add_argument("--proxy", "-p", help="代理地址，如 http://127.0.0.1:7897")
    parser.add_argument("--output", "-o", help="输出 CSV 文件路径（可选）")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        console.print("[red]错误：请提供 --api-key 或设置 YOUTUBE_API_KEY 环境变量[/red]")
        sys.exit(1)

    session = get_session(proxy=args.proxy)

    # ── 最多观看排行 ──
    console.print("\n[bold]▶ 正在获取最多观看排行...[/bold]")
    top_viewed = fetch_all_videos(
        session, api_key, SEARCH_KEYWORDS,
        order="viewCount", max_per_keyword=50,
    )
    if not top_viewed.empty:
        print_table(top_viewed, "🔥 最多观看 TOP 排行榜", sort_by="viewCount", top_n=args.max_results)
    else:
        console.print("[yellow]⚠ 未获取到数据[/yellow]")

    # ── 上升最快排行 ──
    since = (datetime.now(TZ) - timedelta(days=args.rising_days)).isoformat()
    console.print(f"\n[bold]▶ 正在获取近 {args.rising_days} 天发布视频...[/bold]")
    top_rising = fetch_all_videos(
        session, api_key, SEARCH_KEYWORDS,
        order="date", max_per_keyword=50, published_after=since,
    )
    if not top_rising.empty:
        print_table(top_rising, "📈 上升最快 TOP 排行榜（日均观看数排序）", sort_by="velocity", top_n=args.max_results)
    else:
        console.print("[yellow]⚠ 未获取到数据[/yellow]")

    # ── 可选：输出 CSV ──
    if args.output:
        base, ext = os.path.splitext(args.output)
        if not top_viewed.empty:
            top_viewed.to_csv(f"{base}_最多观看{ext}", index=False, encoding="utf-8-sig")
        if not top_rising.empty:
            top_rising.to_csv(f"{base}_上升最快{ext}", index=False, encoding="utf-8-sig")
        console.print(f"\n[green]✓ 已保存至 {base}_*.csv[/green]")

    # ── 摘要 ──
    console.print("\n[bold cyan]═══════════════════════════════════[/bold cyan]")
    console.print(f"  最多观看: {len(top_viewed)} 条")
    console.print(f"  上升最快 (近{args.rising_days}天): {len(top_rising)} 条")
    console.print("[bold cyan]═══════════════════════════════════[/bold cyan]")


if __name__ == "__main__":
    main()
