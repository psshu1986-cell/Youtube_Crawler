"""
YouTube 排行榜 - Flask Web 应用

用法：
  python app.py --api-key YOUR_KEY --proxy http://127.0.0.1:7897
  然后打开 http://127.0.0.1:5000
"""

import argparse
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, render_template, request, jsonify

from youtube_api import DEFAULT_KEYWORDS, fetch_rankings

app = Flask(__name__)

# 全局配置
API_KEY = None
PROXY = None


@app.route("/")
def index():
    api_base = request.host_url.rstrip("/")
    return render_template("index.html", keywords=DEFAULT_KEYWORDS, api_base=api_base)


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效请求"}), 400

    api_key = data.get("apiKey") or API_KEY
    if not api_key:
        return jsonify({"error": "未提供 API Key，请在页面中输入或在启动时指定 --api-key"}), 400

    keywords = data.get("keywords", DEFAULT_KEYWORDS)
    rising_days = int(data.get("risingDays", 60))
    max_per_keyword = int(data.get("maxPerKeyword", 30))

    try:
        top_viewed, top_rising = fetch_rankings(
            api_key, keywords=keywords, proxy=PROXY,
            rising_days=rising_days, max_per_keyword=max_per_keyword,
        )
        return jsonify({
            "topViewed": top_viewed[:30],
            "topRising": top_rising[:30],
            "totalViewed": len(top_viewed),
            "totalRising": len(top_rising),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def main():
    global API_KEY, PROXY

    parser = argparse.ArgumentParser(description="YouTube 排行榜 Web 服务")
    parser.add_argument("--api-key", help="YouTube Data API Key（可选，前端也可输入）")
    parser.add_argument("--proxy", "-p", help="代理地址，如 http://127.0.0.1:7897")
    parser.add_argument("--port", type=int, default=5000, help="服务端口")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    args = parser.parse_args()

    API_KEY = args.api_key or os.environ.get("YOUTUBE_API_KEY")
    if not API_KEY:
        print("▶ API Key 未预设，用户可在前端页面输入")
    else:
        print("▶ 已加载 API Key（也可在前端覆盖）")

    PROXY = args.proxy

    print(f"▶ 启动 Web 服务: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
