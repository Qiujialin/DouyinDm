"""
获取抖音直播间的真实 room_id
"""
import json
import hashlib
import random
import string
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import execjs
import os

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36 Core/1.116.567.400 QQBrowser/19.7.6764.400"
DEFAULT_COOKIE = "ttwid=1%7CB1qls3GdnZhUov9o2NxOMxxYS2ff6OSvEWbv0ytbES4%7C1680522049%7C280d802d6d478e3e78d0c807f7c487e7ffec0ae4e5fdd6a0fe74c3c6af149511"


def generate_ms_token(length=107):
    """生成随机 msToken"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def get_abogus_signature(url, user_agent):
    """
    生成 a_bogus 签名（用于 API 请求）
    """
    js_path = os.path.join(os.path.dirname(__file__), 'douyin_sdk.js')

    if not os.path.exists(js_path):
        raise FileNotFoundError(f"JS SDK file not found at {js_path}")

    with open(js_path, 'r', encoding='utf-8') as f:
        js_code = f.read()

    # 加载 JS SDK 中的 getABogus 函数
    # 注意：douyin_sdk.js 中应该包含 getABogus 函数
    # 如果没有，需要从 pure_live 的 douyin_sign.dart 中提取 kABogus 部分

    ctx = execjs.compile(js_code)

    ms_token = generate_ms_token(107)
    params = f'{url}&msToken={ms_token}'.split('?')[1]
    query = params.split("?")[1] if "?" in params else params

    try:
        a_bogus = ctx.call("getABogus", query, user_agent)
        new_url = f'{url}&msToken={ms_token}&a_bogus={a_bogus}'
        return new_url
    except Exception as e:
        print(f"⚠️  a_bogus 签名生成失败: {e}")
        # 如果签名失败，尝试不带签名访问
        return url


def get_real_room_id(web_rid):
    """
    通过 web_rid 获取真实的 room_id

    Args:
        web_rid: 网页 URL 中的 ID（如 4253196531）

    Returns:
        dict: {
            'room_id': 真实的房间 ID,
            'web_rid': 网页 RID,
            'title': 直播间标题,
            'status': 直播状态,
            'owner': 主播信息
        }
    """
    print(f"🔍 正在获取房间信息...")
    print(f"📺 Web RID: {web_rid}")

    # 构建 API URL
    api_url = "https://live.douyin.com/webcast/room/web/enter/"
    params = {
        "aid": "6383",
        "app_name": "douyin_web",
        "live_id": "1",
        "device_platform": "web",
        "enter_from": "web_live",
        "web_rid": web_rid,
        "room_id_str": "",
        "enter_source": "",
        "Room-Enter-User-Login-Ab": "0",
        "is_need_double_stream": "false",
        "cookie_enabled": "true",
        "screen_width": "1920",
        "screen_height": "1080",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Mozilla",
        "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    url = f"{api_url}?{urlencode(params)}"

    # 尝试添加 a_bogus 签名
    try:
        url = get_abogus_signature(url, USER_AGENT)
        print(f"✅ 已添加 a_bogus 签名")
    except Exception as e:
        print(f"⚠️  跳过 a_bogus 签名: {e}")

    # 发送请求
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": DEFAULT_COOKIE,
        "Referer": f"https://live.douyin.com/{web_rid}",
    }

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

            if data.get("status_code") != 0:
                print(f"❌ API 返回错误: {data.get('status_msg', 'Unknown error')}")
                return None

            room_data = data["data"]["data"][0]
            user_data = data["data"]["user"]

            room_id = room_data["id_str"]
            title = room_data.get("title", "")
            status = room_data.get("status", 0)  # 2 = 直播中
            owner = room_data.get("owner", {})

            print(f"✅ 获取成功！")
            print(f"📺 真实 room_id: {room_id}")
            print(f"📝 标题: {title}")
            print(f"👤 主播: {owner.get('nickname', 'Unknown')}")
            print(f"🔴 状态: {'直播中' if status == 2 else '未开播'}")

            return {
                "room_id": room_id,
                "web_rid": web_rid,
                "title": title,
                "status": status,
                "owner": owner,
                "user_data": user_data,
            }

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1:
        web_rid = sys.argv[1]
    else:
        web_rid = "4253196531"

    print("=" * 60)
    print("🎬 抖音直播间真实 Room ID 获取工具")
    print("=" * 60)
    print()

    result = get_real_room_id(web_rid)

    if result:
        print()
        print("=" * 60)
        print("📋 使用方法:")
        print("=" * 60)
        print(f"在代码中使用:")
        print(f'  ROOM_ID = "{result["room_id"]}"')
        print()
        print(f"或运行:")
        print(f'  python douyin_danmaku.py')
        print(f'  # 修改 ROOM_ID = "{result["room_id"]}"')
        print("=" * 60)
    else:
        print()
        print("❌ 无法获取 room_id")
        print("💡 建议:")
        print("  1. 确认 web_rid 正确")
        print("  2. 检查网络连接")
        print("  3. 尝试使用浏览器开发者工具手动查找")


if __name__ == "__main__":
    main()
