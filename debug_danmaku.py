"""
调试版本 - 查看详细的消息接收情况
"""
import sys
import websocket
import ssl
import time
import gzip
import threading
from douyin_sign import get_signature, generate_ms_token
from douyin_pb2 import PushFrame, Response

# 常量定义
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36 Core/1.116.567.400 QQBrowser/19.7.6764.400"
WS_URL_BASE = "wss://webcast3-ws-web-lq.douyin.com/webcast/im/push/v2/"
DEFAULT_COOKIE = "ttwid=1%7CB1qls3GdnZhUov9o2NxOMxxYS2ff6OSvEWbv0ytbES4%7C1680522049%7C280d802d6d478e3e78d0c807f7c487e7ffec0ae4e5fdd6a0fe74c3c6af149511"
HEARTBEAT_INTERVAL = 10

class DouyinDanmakuDebug:
    """抖音弹幕接收器 - 调试版本"""

    def __init__(self, room_id, cookie=None):
        self.room_id = room_id
        self.unique_id = generate_ms_token(12)
        self.cookie = cookie or DEFAULT_COOKIE
        self.ws = None
        self.heartbeat_timer = None
        self.running = False
        self.message_count = 0

    def construct_ws_url(self):
        """构建 WebSocket URL"""
        signature = get_signature(self.room_id, self.unique_id)
        if not signature:
            raise Exception("Failed to generate signature")

        ts = int(time.time() * 1000)

        params = {
            "app_name": "douyin_web",
            "version_code": "180800",
            "webcast_sdk_version": "1.3.0",
            "update_version_code": "1.3.0",
            "compress": "gzip",
            # 注意：pure_live 中 internal_ext 是被注释掉的
            # "internal_ext": f"internal_src:dim|wss_push_room_id:{self.room_id}|wss_push_did:{self.unique_id}|dim_log_id:202302171547011A03AD2B8D4AD9D56975|fetch_time:{ts}|seq:1|wss_info:0-{ts}-0-0|wrds_kvs:WebcastRoomStatsMessage-{ts}_WebcastRoomRankMessage-{ts}_AudienceGiftSyncData-{ts}_HighlightContainerSyncData-2",
            "cursor": f"h-1_t-{ts}_r-1_d-1_u-1",
            "host": "https://live.douyin.com",
            "aid": "6383",
            "live_id": "1",
            "did_rule": "3",
            "debug": "false",
            "maxCacheMessageNumber": "20",
            "endpoint": "live_pc",
            "support_wrds": "1",
            "im_path": "/webcast/im/fetch/",
            "user_unique_id": self.unique_id,
            "device_platform": "web",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Mozilla",
            "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "browser_online": "true",
            "tz_name": "Asia/Shanghai",
            "identity": "audience",
            "room_id": self.room_id,
            "heartbeatDuration": "0",
            "signature": signature
        }

        from urllib.parse import urlencode
        query = urlencode(params)
        return f"{WS_URL_BASE}?{query}"

    def on_open(self, ws):
        """连接打开回调"""
        print("=" * 60, flush=True)
        print("✅ WebSocket 连接成功！", flush=True)
        print("=" * 60, flush=True)
        self.running = True
        # 发送加入房间消息（关键步骤！）
        self.join_room()
        # 启动心跳定时器
        self.start_heartbeat()

    def on_message(self, ws, message):
        """接收消息回调"""
        self.message_count += 1
        print(f"\n📨 收到消息 #{self.message_count} (大小: {len(message)} 字节)", flush=True)

        try:
            self.decode_message(message)
        except Exception as e:
            print(f"❌ 消息解析错误: {e}", flush=True)
            import traceback
            traceback.print_exc()

    def on_error(self, ws, error):
        """错误回调"""
        print(f"\n❌ WebSocket 错误: {error}", flush=True)

    def on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        print(f"\n🔌 连接已关闭: {close_status_code} - {close_msg}", flush=True)
        print(f"📊 总共收到 {self.message_count} 条消息", flush=True)
        self.running = False
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()

    def decode_message(self, data):
        """解码 Protobuf 消息"""
        print("  🔍 开始解析 PushFrame...", flush=True)

        # 解析 PushFrame
        push_frame = PushFrame()
        push_frame.ParseFromString(data)

        print(f"  📦 PushFrame - logId: {push_frame.logId}, payloadType: {push_frame.payloadType}", flush=True)

        # GZIP 解压
        if push_frame.payload:
            print(f"  🗜️  解压 payload (压缩大小: {len(push_frame.payload)} 字节)...", flush=True)
            try:
                decompressed = gzip.decompress(push_frame.payload)
                print(f"  ✅ 解压成功 (解压后: {len(decompressed)} 字节)", flush=True)

                response = Response()
                response.ParseFromString(decompressed)

                print(f"  📋 Response - needAck: {response.needAck}, 消息数: {len(response.messagesList)}", flush=True)

                # 发送 ACK（如果需要）
                if response.needAck:
                    print(f"  📤 发送 ACK...", flush=True)
                    self.send_ack(push_frame.logId, response.internalExt)

                # 处理消息列表
                for i, msg in enumerate(response.messagesList):
                    print(f"  📬 消息 {i+1}/{len(response.messagesList)}: {msg.method}", flush=True)
                    self.handle_message(msg)

            except Exception as e:
                print(f"  ❌ 解压或解析失败: {e}", flush=True)
                import traceback
                traceback.print_exc()
        else:
            print(f"  ⚠️  PushFrame 没有 payload", flush=True)

    def handle_message(self, msg):
        """处理不同类型的消息"""
        print(f"    🎯 处理消息类型: {msg.method}", flush=True)

        if msg.method == "WebcastChatMessage":
            try:
                from douyin_pb2 import ChatMessage
                chat_msg = ChatMessage()
                chat_msg.ParseFromString(msg.payload)
                print(f"    💬 [{chat_msg.user.nickName}]: {chat_msg.content}", flush=True)
            except Exception as e:
                print(f"    ❌ 聊天消息解析失败: {e}", flush=True)

        elif msg.method == "WebcastRoomUserSeqMessage":
            try:
                from douyin_pb2 import RoomUserSeqMessage
                online_msg = RoomUserSeqMessage()
                online_msg.ParseFromString(msg.payload)
                print(f"    👥 在线人数: {online_msg.totalUser}", flush=True)
            except Exception as e:
                print(f"    ❌ 在线人数解析失败: {e}", flush=True)

        elif msg.method == "WebcastGiftMessage":
            print(f"    🎁 收到礼物消息", flush=True)
        elif msg.method == "WebcastMemberMessage":
            print(f"    👋 用户进入/离开直播间", flush=True)
        elif msg.method == "WebcastLikeMessage":
            print(f"    ❤️ 收到点赞消息", flush=True)
        else:
            print(f"    ❓ 未知消息类型: {msg.method}", flush=True)

    def send_ack(self, log_id, internal_ext):
        """发送 ACK 确认"""
        try:
            ack_frame = PushFrame()
            ack_frame.logId = log_id
            ack_frame.payloadType = "ack"
            ack_frame.payload = internal_ext.encode('utf-8')
            self.ws.send(ack_frame.SerializeToString(), opcode=websocket.ABNF.OPCODE_BINARY)
            print(f"  ✅ ACK 发送成功", flush=True)
        except Exception as e:
            print(f"  ❌ ACK 发送失败: {e}", flush=True)

    def heartbeat(self):
        """发送心跳"""
        if self.running and self.ws:
            try:
                hb_frame = PushFrame()
                hb_frame.payloadType = "hb"
                self.ws.send(hb_frame.SerializeToString(), opcode=websocket.ABNF.OPCODE_BINARY)
                print(f"\n💓 发送心跳 (时间: {time.strftime('%H:%M:%S')})", flush=True)
            except Exception as e:
                print(f"\n❌ 心跳发送失败: {e}", flush=True)

    def join_room(self):
        """加入房间（连接成功后立即调用）"""
        try:
            hb_frame = PushFrame()
            hb_frame.payloadType = "hb"
            self.ws.send(hb_frame.SerializeToString(), opcode=websocket.ABNF.OPCODE_BINARY)
            print("🚪 已发送加入房间消息", flush=True)
        except Exception as e:
            print(f"❌ 加入房间失败: {e}", flush=True)

    def start_heartbeat(self):
        """启动心跳定时器"""
        def heartbeat_loop():
            while self.running:
                time.sleep(HEARTBEAT_INTERVAL)
                self.heartbeat()

        self.heartbeat_timer = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_timer.start()
        print("💓 心跳定时器已启动", flush=True)

    def connect(self):
        """建立连接"""
        print("=" * 60, flush=True)
        print("🎬 抖音弹幕接收器 - 调试模式", flush=True)
        print("=" * 60, flush=True)
        print(f"📺 房间 ID: {self.room_id}", flush=True)
        print(f"🆔 用户 ID: {self.unique_id}", flush=True)
        print(f"🍪 Cookie: {self.cookie[:50]}...", flush=True)
        print("=" * 60, flush=True)

        url = self.construct_ws_url()
        print(f"🔗 正在连接...", flush=True)

        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": self.cookie,
            "Origin": "https://live.douyin.com"
        }

        # 启用调试模式
        websocket.enableTrace(False)  # 设为 True 可以看到更详细的 WebSocket 日志

        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def close(self):
        """关闭连接"""
        self.running = False
        if self.ws:
            self.ws.close()


def main():
    """主函数"""
    import signal

    # 房间 ID - 使用真实的 room_id！
    ROOM_ID = "7604135614396582671"  # 真实的 room_id（不是 web_rid）

    danmaku = DouyinDanmakuDebug(ROOM_ID)

    def signal_handler(sig, frame):
        print('\n\n⏹️  用户中断，正在关闭...', flush=True)
        danmaku.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        danmaku.connect()
    except Exception as e:
        print(f"\n❌ 错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        danmaku.close()


if __name__ == "__main__":
    main()
