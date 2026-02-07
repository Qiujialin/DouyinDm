"""
完整的抖音弹幕接收实现
基于 pure_live 项目的 Dart 实现移植
"""
import websocket
import ssl
import time
import gzip
import threading
from douyin_sign import get_signature, generate_ms_token
from douyin_pb2 import PushFrame, Response, ChatMessage, RoomUserSeqMessage

# 常量定义
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36 Core/1.116.567.400 QQBrowser/19.7.6764.400"
WS_URL_BASE = "wss://webcast3-ws-web-lq.douyin.com/webcast/im/push/v2/"
DEFAULT_COOKIE = "ttwid=1%7CB1qls3GdnZhUov9o2NxOMxxYS2ff6OSvEWbv0ytbES4%7C1680522049%7C280d802d6d478e3e78d0c807f7c487e7ffec0ae4e5fdd6a0fe74c3c6af149511"
HEARTBEAT_INTERVAL = 10  # 心跳间隔（秒）


class DouyinDanmaku:
    """抖音弹幕接收器"""

    def __init__(self, room_id, cookie=None):
        self.room_id = room_id
        self.unique_id = generate_ms_token(12)
        self.cookie = cookie or DEFAULT_COOKIE
        self.ws = None
        self.heartbeat_timer = None
        self.running = False

    def construct_ws_url(self):
        """构建 WebSocket URL"""
        signature = get_signature(self.room_id, self.unique_id)
        if not signature:
            raise Exception("Failed to generate signature")

        # 使用当前时间戳
        ts = int(time.time() * 1000)

        # 参数配置（匹配 pure_live 实现）
        params = {
            "app_name": "douyin_web",
            "version_code": "180800",
            "webcast_sdk_version": "1.3.0",
            "update_version_code": "1.3.0",
            "compress": "gzip",
            # 注意：pure_live 中 internal_ext 是被注释掉的，我们也尝试不使用它
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

        # 构建 URL
        from urllib.parse import urlencode
        query = urlencode(params)
        return f"{WS_URL_BASE}?{query}"

    def on_open(self, ws):
        """连接打开回调"""
        print("✅ WebSocket 连接成功！")
        self.running = True
        # 发送加入房间消息（关键步骤！）
        self.join_room()
        # 启动心跳定时器
        self.start_heartbeat()

    def on_message(self, ws, message):
        """接收消息回调"""
        try:
            self.decode_message(message)
        except Exception as e:
            print(f"❌ 消息解析错误: {e}")

    def on_error(self, ws, error):
        """错误回调"""
        print(f"❌ WebSocket 错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        print(f"🔌 连接已关闭: {close_status_code} - {close_msg}")
        self.running = False
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()

    def decode_message(self, data):
        """解码 Protobuf 消息"""
        # 解析 PushFrame
        push_frame = PushFrame()
        push_frame.ParseFromString(data)

        # GZIP 解压
        if push_frame.payload:
            decompressed = gzip.decompress(push_frame.payload)
            response = Response()
            response.ParseFromString(decompressed)

            # 发送 ACK（如果需要）
            if response.needAck:
                self.send_ack(push_frame.logId, response.internalExt)

            # 处理消息列表
            for msg in response.messagesList:
                self.handle_message(msg)

    def handle_message(self, msg):
        """处理不同类型的消息"""
        if msg.method == "WebcastChatMessage":
            self.handle_chat_message(msg.payload)
        elif msg.method == "WebcastRoomUserSeqMessage":
            self.handle_online_message(msg.payload)
        elif msg.method == "WebcastGiftMessage":
            pass  # 礼物消息
        elif msg.method == "WebcastMemberMessage":
            pass  # 用户进入/离开直播间
        elif msg.method == "WebcastLikeMessage":
            pass  # 点赞消息

    def handle_chat_message(self, payload):
        """处理聊天消息"""
        chat_msg = ChatMessage()
        chat_msg.ParseFromString(payload)
        print(f"💬 [{chat_msg.user.nickName}]: {chat_msg.content}")

    def handle_online_message(self, payload):
        """处理在线人数消息"""
        online_msg = RoomUserSeqMessage()
        online_msg.ParseFromString(payload)
        # 不打印在线人数，避免刷屏
        pass

    def send_ack(self, log_id, internal_ext):
        """发送 ACK 确认"""
        ack_frame = PushFrame()
        ack_frame.logId = log_id
        ack_frame.payloadType = "ack"
        ack_frame.payload = internal_ext.encode('utf-8')
        self.ws.send(ack_frame.SerializeToString(), opcode=websocket.ABNF.OPCODE_BINARY)

    def heartbeat(self):
        """发送心跳"""
        if self.running and self.ws:
            try:
                hb_frame = PushFrame()
                hb_frame.payloadType = "hb"
                self.ws.send(hb_frame.SerializeToString(), opcode=websocket.ABNF.OPCODE_BINARY)
                print("💓 发送心跳")
            except Exception as e:
                print(f"❌ 心跳发送失败: {e}")

    def join_room(self):
        """加入房间（连接成功后立即调用）"""
        try:
            hb_frame = PushFrame()
            hb_frame.payloadType = "hb"
            self.ws.send(hb_frame.SerializeToString(), opcode=websocket.ABNF.OPCODE_BINARY)
            print("🚪 已发送加入房间消息")
        except Exception as e:
            print(f"❌ 加入房间失败: {e}")

    def start_heartbeat(self):
        """启动心跳定时器"""
        def heartbeat_loop():
            while self.running:
                time.sleep(HEARTBEAT_INTERVAL)
                self.heartbeat()

        self.heartbeat_timer = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_timer.start()

    def connect(self):
        """建立连接"""
        url = self.construct_ws_url()
        print(f"🔗 正在连接: {self.room_id}")

        # 请求头（匹配 pure_live 实现）
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": self.cookie,
            "Origin": "https://live.douyin.com"
        }

        # 创建 WebSocket 连接
        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        # 运行（阻塞）
        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def close(self):
        """关闭连接"""
        self.running = False
        if self.ws:
            self.ws.close()


def main():
    """主函数"""
    # 测试房间 ID
    ROOM_ID = "7604135614396582671"

    # 创建弹幕接收器
    danmaku = DouyinDanmaku(ROOM_ID)

    try:
        # 连接并接收弹幕
        danmaku.connect()
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
        danmaku.close()
    except Exception as e:
        print(f"❌ 错误: {e}")
        danmaku.close()


if __name__ == "__main__":
    main()
