"""
YouTube 中国神仙视频排行榜 - 核心 API 模块
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

TZ = timezone.utc
YT_API = "https://www.googleapis.com/youtube/v3"

# 默认搜索关键词（用户可自定义）
DEFAULT_KEYWORDS = [
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

EXCLUDE_KEYWORDS = [
    "游戏", "攻略", "MMO", "手游", "cosplay", "搞笑",
    "神仙豆腐", "神仙居", "神仙球", "神仙翻唱", "神仙水",
    "美食", "菜谱", "景区", "旅游", "羽毛球",
    "钓鱼", "钓法", "鱼饵",
    "翻唱", "cover", "弹唱",
    "shorts", "#shorts",
]


def get_session(proxy: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    session.timeout = 30
    return session


def api_get(session: requests.Session, path: str, params: dict) -> dict | None:
    url = f"{YT_API}/{path}"
    try:
        resp = session.get(url, params=params)
        if resp.status_code == 429:
            raise RuntimeError(
                "YouTube API 配额已用完（每日 10,000 units）。"
                "请明天再试，或前往 https://console.cloud.google.com/ 增加配额。"
            )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        print(f"[错误] 请求超时: {url}")
    except requests.exceptions.ConnectionError as e:
        print(f"[错误] 连接失败 (检查代理/网络): {e}")
    except requests.exceptions.HTTPError as e:
        print(f"[错误] API 错误 ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        raise  # 让上层捕获配額错误等
    return None


def search_videos(
    session: requests.Session, api_key: str, query: str,
    order: str = "viewCount", max_results: int = 50,
    published_after: str = None, video_duration: str = "long",
) -> list[dict]:
    params = dict(
        part="snippet",
        q=query,
        type="video",
        order=order,
        maxResults=min(max_results, 50),
        relevanceLanguage="zh",
        key=api_key,
    )
    if video_duration:
        params["videoDuration"] = video_duration
    if published_after:
        params["publishedAfter"] = published_after

    data = api_get(session, "search", params)
    if not data:
        return []

    results = []
    for item in data.get("items", []):
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
        })
    return results


def get_video_stats(
    session: requests.Session, api_key: str, video_ids: list[str],
    min_duration_sec: int = 300,
) -> dict[str, dict]:
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
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not m:
        return 0
    h, m_, s = [int(g) if g else 0 for g in m.groups()]
    return h * 3600 + m_ * 60 + s


def fetch_by_keywords(
    session: requests.Session, api_key: str, keywords: list[str],
    order: str, max_per_keyword: int = 50, published_after: str = None,
    video_duration: str = "long",
) -> list[dict]:
    seen = set()
    rows = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        results = search_videos(
            session, api_key, kw, order=order,
            max_results=max_per_keyword, published_after=published_after,
            video_duration=video_duration,
        )
        for r in results:
            if r["videoId"] not in seen:
                seen.add(r["videoId"])
                rows.append(r)
    if not rows:
        return []

    video_ids = [r["videoId"] for r in rows]
    stats = get_video_stats(session, api_key, video_ids)

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
            "velocity": round(s["viewCount"] / days_since),
            "url": f"https://youtu.be/{r['videoId']}",
        })
    return records


def fetch_rankings(
    api_key: str, keywords: list[str] = None,
    proxy: str = None, rising_days: int = 60,
    max_per_keyword: int = 50,
) -> tuple[list[dict], list[dict]]:
    """返回 (最多观看排行, 上升最快排行)"""
    keywords = keywords or DEFAULT_KEYWORDS
    session = get_session(proxy)

    # 最多观看
    top_viewed = fetch_by_keywords(
        session, api_key, keywords,
        order="viewCount", max_per_keyword=max_per_keyword,
    )

    # 上升最快
    since = (datetime.now(TZ) - timedelta(days=rising_days)).isoformat()
    top_rising = fetch_by_keywords(
        session, api_key, keywords,
        order="date", max_per_keyword=max_per_keyword,
        published_after=since,
    )

    # 按 velocity 排序
    top_rising.sort(key=lambda x: x["velocity"], reverse=True)

    return top_viewed, top_rising
