// Cloudflare Pages Function - /api/search
// 處理 YouTube API 搜索請求，返回五個維度的排行榜

const YT_API = 'https://www.googleapis.com/youtube/v3';

// YouTube API 調用工具（自帶超時）
async function apiFetch(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    return resp;
  } catch (e) {
    clearTimeout(timeout);
    if (e.name === 'AbortError') throw new Error('請求 YouTube API 超時，請稍後重試');
    throw e;
  }
}

async function apiGet(params) {
  const url = YT_API + '/search?' + new URLSearchParams(params);
  const resp = await apiFetch(url);
  if (resp.status === 429) {
    throw new Error('YouTube API 配額已用完（每日 10,000 units）。請明天再試，或前往 https://console.cloud.google.com/ 增加配額。');
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API 錯誤 (${resp.status}): ${text.slice(0, 200)}`);
  }
  return resp.json();
}

async function videosGet(params) {
  const url = YT_API + '/videos?' + new URLSearchParams(params);
  const resp = await apiFetch(url);
  if (resp.status === 429) {
    throw new Error('YouTube API 配額已用完。');
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Videos API 錯誤 (${resp.status}): ${text.slice(0, 200)}`);
  }
  return resp.json();
}

// ISO 8601 持續時間轉秒
function isoDurationToSeconds(dur) {
  const m = dur.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!m) return 0;
  const [, h, min, s] = m.map(v => parseInt(v) || 0);
  return h * 3600 + min * 60 + s;
}

// 搜索單一關鍵詞
async function searchKeyword(apiKey, query, order, publishedAfter) {
  const params = {
    part: 'snippet',
    q: query,
    type: 'video',
    order: order,
    maxResults: 50,
    key: apiKey,
  };
  if (publishedAfter) params.publishedAfter = publishedAfter;

  const data = await apiGet(params);
  if (!data || !data.items) return [];

  const results = [];
  for (const item of data.items) {
    const videoId = item.id.videoId;
    const title = item.snippet.title;
    // 過濾 shorts
    if (title.toLowerCase().includes('#shorts')) continue;
    results.push({
      videoId,
      title,
      channelId: item.snippet.channelId,
      channelTitle: item.snippet.channelTitle,
      publishedAt: item.snippet.publishedAt,
    });
  }
  return results;
}

// 批量獲取影片統計
async function getStats(apiKey, videoIds) {
  const statsMap = {};
  for (let i = 0; i < videoIds.length; i += 50) {
    const batch = videoIds.slice(i, i + 50);
    const data = await videosGet({
      part: 'statistics,contentDetails',
      id: batch.join(','),
      key: apiKey,
    });
    if (!data || !data.items) continue;
    for (const item of data.items) {
      const vid = item.id;
      const rawDur = item.contentDetails?.duration || 'PT0S';
      const durSec = isoDurationToSeconds(rawDur);
      if (durSec < 300) continue; // 過濾短於5分鐘
      const stat = item.statistics || {};
      statsMap[vid] = {
        viewCount: parseInt(stat.viewCount) || 0,
        likeCount: parseInt(stat.likeCount) || 0,
        commentCount: parseInt(stat.commentCount) || 0,
      };
    }
  }
  return statsMap;
}

export async function onRequest(context) {
  const { request } = context;

  // 只接受 POST
  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ error: '僅接受 POST 請求' }), {
      status: 405, headers: { 'Content-Type': 'application/json', 'Allow': 'POST' },
    });
  }

  try {
    const data = await request.json();
    const apiKey = data.apiKey;
    if (!apiKey) {
      return new Response(JSON.stringify({ error: '未提供 API Key' }), {
        status: 400, headers: { 'Content-Type': 'application/json' },
      });
    }

    const keywords = data.keywords || [];
    const risingDays = data.risingDays || 60;
    const maxPerKeyword = data.maxPerKeyword || 30;

    if (!keywords.length) {
      return new Response(JSON.stringify({ error: '請提供至少一個搜索關鍵詞' }), {
        status: 400, headers: { 'Content-Type': 'application/json' },
      });
    }

    // === 最多觀看 ===
    const viewedResults = [];
    const seen = new Set();
    for (const kw of keywords) {
      const items = await searchKeyword(apiKey, kw, 'viewCount');
      for (const item of items) {
        if (!seen.has(item.videoId)) {
          seen.add(item.videoId);
          viewedResults.push(item);
        }
      }
    }

    // 獲取統計數據
    const allIds = viewedResults.map(r => r.videoId);
    const stats = await getStats(apiKey, allIds);

    // 合併數據
    function buildRecords(rows) {
      const records = [];
      const now = Date.now();
      for (const r of rows) {
        const s = stats[r.videoId];
        if (!s) continue;
        const published = new Date(r.publishedAt).getTime();
        const daysSince = Math.max((now - published) / 86400000, 0.01);
        records.push({
          videoId: r.videoId,
          title: r.title,
          channelTitle: r.channelTitle,
          publishedAt: r.publishedAt.replace('T', ' ').replace('Z', '').slice(0, 16),
          viewCount: s.viewCount,
          likeCount: s.likeCount,
          commentCount: s.commentCount,
          daysSincePublished: Math.round(daysSince * 10) / 10,
          velocity: Math.round(s.viewCount / daysSince),
          url: `https://youtu.be/${r.videoId}`,
        });
      }
      return records;
    }

    const topViewed = buildRecords(viewedResults);

    // === 上升最快 ===
    const since = new Date(Date.now() - risingDays * 86400000).toISOString();
    seen.clear();
    const risingResults = [];
    for (const kw of keywords) {
      const items = await searchKeyword(apiKey, kw, 'date', since);
      for (const item of items) {
        if (!seen.has(item.videoId)) {
          seen.add(item.videoId);
          risingResults.push(item);
        }
      }
    }

    const risingStats = await getStats(apiKey, risingResults.map(r => r.videoId));
    // 臨時把 stats 換成 risingStats
    const tempStats = { ...stats, ...risingStats };
    let topRising = [];
    for (const r of risingResults) {
      const s = tempStats[r.videoId];
      if (!s) continue;
      const published = new Date(r.publishedAt).getTime();
      const daysSince = Math.max((Date.now() - published) / 86400000, 0.01);
      topRising.push({
        videoId: r.videoId,
        title: r.title,
        channelTitle: r.channelTitle,
        publishedAt: r.publishedAt.replace('T', ' ').replace('Z', '').slice(0, 16),
        viewCount: s.viewCount,
        likeCount: s.likeCount,
        commentCount: s.commentCount,
        daysSincePublished: Math.round(daysSince * 10) / 10,
        velocity: Math.round(s.viewCount / daysSince),
        url: `https://youtu.be/${r.videoId}`,
      });
    }
    topRising.sort((a, b) => b.velocity - a.velocity);

    // === 衍生排序 ===
    const topLiked = [...topViewed].sort((a, b) => b.likeCount - a.likeCount);
    const topCommented = [...topViewed].sort((a, b) => b.commentCount - a.commentCount);
    const topEngaged = [...topViewed].sort((a, b) => {
      const ra = (a.likeCount + a.commentCount) / Math.max(a.viewCount, 1);
      const rb = (b.likeCount + b.commentCount) / Math.max(b.viewCount, 1);
      return rb - ra;
    });

    return new Response(JSON.stringify({
      topViewed, topLiked, topCommented, topEngaged, topRising,
      totalViewed: topViewed.length,
      totalRising: topRising.length,
    }), {
      headers: { 'Content-Type': 'application/json' },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: { 'Content-Type': 'application/json' },
    });
  }
}
