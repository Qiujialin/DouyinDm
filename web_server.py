"""
抖音弹幕 Web 服务器
实时显示弹幕，支持正则表达式过滤
"""
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import re
import time
from collections import deque
from douyin_danmaku import DouyinDanmaku
from get_real_room_id import get_real_room_id

app = Flask(__name__)
app.config['SECRET_KEY'] = 'douyin_danmaku_secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量
danmaku_receiver = None
danmaku_buffer = deque(maxlen=100)  # 保存最近100条弹幕
current_filter = None  # 当前的正则表达式过滤器
is_running = False


class WebDanmakuReceiver(DouyinDanmaku):
    """Web 版弹幕接收器"""

    def handle_chat_message(self, payload):
        """处理聊天消息 - 重写以发送到 Web"""
        from douyin_pb2 import ChatMessage
        chat_msg = ChatMessage()
        chat_msg.ParseFromString(payload)

        message = chat_msg.content
        username = chat_msg.user.nickName
        timestamp = time.strftime('%H:%M:%S')

        # 应用正则表达式过滤
        if current_filter:
            try:
                if not re.search(current_filter, message):
                    return  # 不匹配，跳过
            except re.error:
                pass  # 正则表达式错误，不过滤

        # 构建弹幕数据
        danmaku_data = {
            'message': message,
            'username': username,
            'timestamp': timestamp
        }

        # 添加到缓冲区
        danmaku_buffer.append(danmaku_data)

        # 发送到所有连接的客户端
        socketio.emit('new_danmaku', danmaku_data, namespace='/')

        # 控制台输出
        print(f"[{timestamp}] {message}")


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/start', methods=['POST'])
def start_danmaku():
    """启动弹幕接收"""
    global danmaku_receiver, is_running

    if is_running:
        return jsonify({'error': '已经在运行中'}), 400

    data = request.json
    web_rid = data.get('web_rid')

    if not web_rid:
        return jsonify({'error': '请提供 web_rid'}), 400

    try:
        # 获取真实 room_id
        print(f"正在获取房间信息: {web_rid}")
        room_info = get_real_room_id(web_rid)

        if not room_info:
            return jsonify({'error': '无法获取房间信息'}), 400

        room_id = room_info['room_id']
        title = room_info['title']
        owner = room_info['owner'].get('nickname', 'Unknown')

        # 创建弹幕接收器
        danmaku_receiver = WebDanmakuReceiver(room_id)

        # 在后台线程中运行
        def run_receiver():
            global is_running
            is_running = True
            try:
                danmaku_receiver.connect()
            except Exception as e:
                print(f"弹幕接收错误: {e}")
            finally:
                is_running = False

        thread = threading.Thread(target=run_receiver, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'room_id': room_id,
            'title': title,
            'owner': owner
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_danmaku():
    """停止弹幕接收"""
    global danmaku_receiver, is_running

    if danmaku_receiver:
        danmaku_receiver.close()
        danmaku_receiver = None

    is_running = False

    return jsonify({'success': True})


@app.route('/api/filter', methods=['POST'])
def set_filter():
    """设置正则表达式过滤器"""
    global current_filter

    data = request.json
    filter_pattern = data.get('pattern', '')

    if filter_pattern:
        try:
            # 验证正则表达式
            re.compile(filter_pattern)
            current_filter = filter_pattern
            return jsonify({'success': True, 'pattern': filter_pattern})
        except re.error as e:
            return jsonify({'error': f'正则表达式错误: {str(e)}'}), 400
    else:
        current_filter = None
        return jsonify({'success': True, 'pattern': None})


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取历史弹幕"""
    count = int(request.args.get('count', 20))
    history = list(danmaku_buffer)[-count:]
    return jsonify({'danmaku': history})


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取运行状态"""
    return jsonify({
        'is_running': is_running,
        'filter': current_filter,
        'buffer_size': len(danmaku_buffer)
    })


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print('客户端已连接')
    # 发送最近20条弹幕
    history = list(danmaku_buffer)[-20:]
    emit('history', {'danmaku': history})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    print('客户端已断开')


if __name__ == '__main__':
    print("=" * 60)
    print("🎬 抖音弹幕 Web 服务器")
    print("=" * 60)
    print("📡 服务器地址: http://localhost:8080")
    print("💡 在浏览器中打开上述地址即可使用")
    print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
