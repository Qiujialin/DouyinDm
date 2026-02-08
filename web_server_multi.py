"""
抖音弹幕 Web 服务器 - 多直播间并发版本
支持同时监控多个直播间的弹幕
"""
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import re
import time
from datetime import datetime, timezone, timedelta
import json
import os
from collections import deque
from douyin_danmaku import DouyinDanmaku
from get_real_room_id import get_real_room_id

app = Flask(__name__)
app.config['SECRET_KEY'] = 'douyin_danmaku_multi_secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 配置文件路径
CONFIG_FILE = 'douyin_config.json'

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

# 全局变量
rooms = {}  # 存储所有直播间：{room_id: {receiver, thread, info, buffer}}
current_filter = None  # 全局正则表达式过滤器
global_buffer = deque(maxlen=200)  # 全局弹幕缓冲区


def save_config():
    """保存配置到文件"""
    config = {
        'filter': current_filter,
        'rooms': []
    }

    # 保存直播间信息（不保存运行时数据）
    for room_id, room_data in rooms.items():
        config['rooms'].append({
            'room_id': room_id,
            'web_rid': room_data['info']['web_rid'],
            'title': room_data['info']['title'],
            'owner': room_data['info']['owner']
        })

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ 配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ 保存配置失败: {e}")


def load_config():
    """从文件加载配置"""
    global current_filter

    if not os.path.exists(CONFIG_FILE):
        print(f"ℹ️  配置文件不存在，将使用默认配置")
        return

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 恢复过滤器
        current_filter = config.get('filter')
        if current_filter:
            print(f"✅ 已恢复过滤器: {current_filter}")

        # 恢复直播间列表
        for room_info in config.get('rooms', []):
            room_id = room_info['room_id']
            rooms[room_id] = {
                'info': room_info,
                'receiver': None,
                'thread': None,
                'is_running': False,
                'buffer': deque(maxlen=100)
            }
            print(f"✅ 已恢复直播间: {room_info['title']} - {room_info['owner']}")

        print(f"✅ 配置加载完成，共 {len(rooms)} 个直播间")

    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        import traceback
        traceback.print_exc()


class MultiRoomDanmakuReceiver(DouyinDanmaku):
    """多直播间弹幕接收器"""

    def __init__(self, room_id, room_info, cookie=None):
        super().__init__(room_id, cookie)
        self.room_info = room_info
        self.web_rid = room_info.get('web_rid', room_id)
        self.title = room_info.get('title', '未知')
        # owner 现在是字符串，不是字典
        self.owner = room_info.get('owner', '未知')

    def handle_chat_message(self, payload):
        """处理聊天消息 - 重写以发送到 Web"""
        from douyin_pb2 import ChatMessage
        chat_msg = ChatMessage()
        chat_msg.ParseFromString(payload)

        message = chat_msg.content
        username = chat_msg.user.nickName
        # 使用北京时间
        timestamp = datetime.now(BEIJING_TZ).strftime('%H:%M:%S')

        # 应用正则表达式过滤
        if current_filter:
            try:
                if not re.search(current_filter, message):
                    # 不匹配，跳过（可选：打印调试信息）
                    # print(f"[过滤] [{self.title}] {message}")
                    return
            except re.error:
                pass  # 正则表达式错误，不过滤

        # 构建弹幕数据
        danmaku_data = {
            'message': message,
            'username': username,
            'timestamp': timestamp,
            'room_id': self.room_id,
            'web_rid': self.web_rid,
            'room_title': self.title,
            'room_owner': self.owner
        }

        # 添加到全局缓冲区
        global_buffer.append(danmaku_data)

        # 添加到房间缓冲区
        if self.room_id in rooms:
            rooms[self.room_id]['buffer'].append(danmaku_data)

        # 发送到所有连接的客户端
        socketio.emit('new_danmaku', danmaku_data, namespace='/')

        # 控制台输出
        print(f"[{timestamp}] [{self.title}] {message}")


@app.route('/')
def index():
    """主页"""
    return render_template('index_multi.html')


@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    """获取所有直播间列表"""
    room_list = []
    for room_id, room_data in rooms.items():
        room_list.append({
            'room_id': room_id,
            'web_rid': room_data['info']['web_rid'],
            'title': room_data['info']['title'],
            'owner': room_data['info']['owner'],
            'is_running': room_data['is_running'],
            'danmaku_count': len(room_data['buffer'])
        })
    return jsonify({'rooms': room_list})


@app.route('/api/add_room', methods=['POST'])
def add_room():
    """添加一个直播间"""
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

        room_id = room_info.get('room_id')
        if not room_id:
            return jsonify({'error': '无法获取 room_id'}), 400

        # 检查是否已存在
        if room_id in rooms:
            return jsonify({'error': '该直播间已在监控中'}), 400

        # 获取主播名称（兼容多种数据格式）
        owner_info = room_info.get('owner', {})
        if isinstance(owner_info, dict):
            owner_name = owner_info.get('nickname', 'Unknown')
        elif isinstance(owner_info, str):
            owner_name = owner_info
        else:
            owner_name = 'Unknown'

        # 获取标题
        title = room_info.get('title', '未知直播间')

        # 创建房间数据
        rooms[room_id] = {
            'info': {
                'room_id': room_id,
                'web_rid': web_rid,
                'title': title,
                'owner': owner_name
            },
            'receiver': None,
            'thread': None,
            'is_running': False,
            'buffer': deque(maxlen=100)
        }

        print(f"✅ 添加成功: {title} - {owner_name}")

        # 保存配置
        save_config()

        return jsonify({
            'success': True,
            'room_id': room_id,
            'web_rid': web_rid,
            'title': title,
            'owner': owner_name
        })

    except Exception as e:
        print(f"❌ 添加失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/start_room/<room_id>', methods=['POST'])
def start_room(room_id):
    """启动指定直播间的弹幕接收"""
    if room_id not in rooms:
        return jsonify({'error': '直播间不存在'}), 404

    room_data = rooms[room_id]

    if room_data['is_running']:
        return jsonify({'error': '该直播间已在运行中'}), 400

    try:
        # 创建弹幕接收器
        receiver = MultiRoomDanmakuReceiver(room_id, room_data['info'])
        room_data['receiver'] = receiver

        # 在后台线程中运行
        def run_receiver():
            room_data['is_running'] = True
            try:
                receiver.connect()
            except Exception as e:
                print(f"直播间 {room_id} 弹幕接收错误: {e}")
            finally:
                room_data['is_running'] = False

        thread = threading.Thread(target=run_receiver, daemon=True)
        thread.start()
        room_data['thread'] = thread

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop_room/<room_id>', methods=['POST'])
def stop_room(room_id):
    """停止指定直播间的弹幕接收"""
    if room_id not in rooms:
        return jsonify({'error': '直播间不存在'}), 404

    room_data = rooms[room_id]

    if room_data['receiver']:
        room_data['receiver'].close()
        room_data['receiver'] = None

    room_data['is_running'] = False

    return jsonify({'success': True})


@app.route('/api/remove_room/<room_id>', methods=['POST'])
def remove_room(room_id):
    """移除一个直播间"""
    if room_id not in rooms:
        return jsonify({'error': '直播间不存在'}), 404

    # 先停止
    room_data = rooms[room_id]
    if room_data['receiver']:
        room_data['receiver'].close()

    # 删除
    del rooms[room_id]

    # 保存配置
    save_config()

    return jsonify({'success': True})


@app.route('/api/start_all', methods=['POST'])
def start_all():
    """启动所有直播间"""
    started = []
    errors = []

    for room_id in list(rooms.keys()):
        try:
            if not rooms[room_id]['is_running']:
                # 直接调用启动逻辑，而不是调用 start_room 函数
                room_data = rooms[room_id]

                # 创建弹幕接收器
                receiver = MultiRoomDanmakuReceiver(room_id, room_data['info'])
                room_data['receiver'] = receiver

                # 在后台线程中运行
                def run_receiver(rid=room_id):
                    rooms[rid]['is_running'] = True
                    try:
                        receiver.connect()
                    except Exception as e:
                        print(f"直播间 {rid} 弹幕接收错误: {e}")
                    finally:
                        rooms[rid]['is_running'] = False

                thread = threading.Thread(target=run_receiver, daemon=True)
                thread.start()
                room_data['thread'] = thread

                started.append(room_id)
        except Exception as e:
            errors.append({'room_id': room_id, 'error': str(e)})

    return jsonify({
        'success': True,
        'started': started,
        'errors': errors
    })


@app.route('/api/stop_all', methods=['POST'])
def stop_all():
    """停止所有直播间"""
    for room_id, room_data in rooms.items():
        if room_data['receiver']:
            room_data['receiver'].close()
            room_data['receiver'] = None
        room_data['is_running'] = False

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
            print(f"✅ 过滤器已设置: {filter_pattern}")

            # 保存配置
            save_config()

            return jsonify({'success': True, 'pattern': filter_pattern})
        except re.error as e:
            print(f"❌ 正则表达式错误: {str(e)}")
            return jsonify({'error': f'正则表达式错误: {str(e)}'}), 400
    else:
        current_filter = None
        print("✅ 过滤器已清除")

        # 保存配置
        save_config()

        return jsonify({'success': True, 'pattern': None})


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取历史弹幕"""
    count = int(request.args.get('count', 20))
    room_id = request.args.get('room_id', None)

    if room_id and room_id in rooms:
        # 获取指定房间的历史
        history = list(rooms[room_id]['buffer'])[-count:]
    else:
        # 获取全局历史
        history = list(global_buffer)[-count:]

    return jsonify({'danmaku': history})


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取运行状态"""
    running_count = sum(1 for room in rooms.values() if room['is_running'])

    return jsonify({
        'total_rooms': len(rooms),
        'running_rooms': running_count,
        'filter': current_filter,
        'global_buffer_size': len(global_buffer)
    })


@app.route('/api/export', methods=['GET'])
def export_config():
    """导出配置"""
    config = {
        'filter': current_filter,
        'rooms': []
    }

    # 导出直播间信息
    for room_id, room_data in rooms.items():
        config['rooms'].append({
            'room_id': room_id,
            'web_rid': room_data['info']['web_rid'],
            'title': room_data['info']['title'],
            'owner': room_data['info']['owner']
        })

    return jsonify(config)


@app.route('/api/import', methods=['POST'])
def import_config():
    """导入配置"""
    global current_filter

    try:
        data = request.json

        if not data:
            return jsonify({'error': '无效的配置数据'}), 400

        imported_count = 0
        skipped_count = 0
        errors = []

        # 导入过滤器
        if 'filter' in data:
            filter_pattern = data['filter']
            if filter_pattern:
                try:
                    re.compile(filter_pattern)
                    current_filter = filter_pattern
                    print(f"✅ 已导入过滤器: {filter_pattern}")
                except re.error as e:
                    errors.append(f"过滤器错误: {str(e)}")
            else:
                current_filter = None

        # 导入直播间
        for room_info in data.get('rooms', []):
            room_id = room_info.get('room_id')
            web_rid = room_info.get('web_rid')
            title = room_info.get('title', '未知')
            owner = room_info.get('owner', '未知')

            if not room_id or not web_rid:
                errors.append(f"直播间数据不完整: {title}")
                continue

            # 检查是否已存在
            if room_id in rooms:
                skipped_count += 1
                continue

            # 添加直播间
            rooms[room_id] = {
                'info': {
                    'room_id': room_id,
                    'web_rid': web_rid,
                    'title': title,
                    'owner': owner
                },
                'receiver': None,
                'thread': None,
                'is_running': False,
                'buffer': deque(maxlen=100)
            }
            imported_count += 1
            print(f"✅ 已导入直播间: {title} - {owner}")

        # 保存配置
        save_config()

        return jsonify({
            'success': True,
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': errors
        })

    except Exception as e:
        print(f"❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    # 发送最近20条弹幕
    history = list(global_buffer)[-20:]
    emit('history', {'danmaku': history})
    # 发送房间列表
    emit('rooms_update', {'rooms': [
        {
            'room_id': room_id,
            'web_rid': room_data['info']['web_rid'],
            'title': room_data['info']['title'],
            'owner': room_data['info']['owner'],
            'is_running': room_data['is_running']
        }
        for room_id, room_data in rooms.items()
    ]})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    pass


if __name__ == '__main__':
    print("=" * 60)
    print("🎬 抖音弹幕 Web 服务器 - 多直播间并发版本")
    print("=" * 60)

    # 加载配置
    load_config()

    # 从环境变量获取端口（Railway/Render 等平台需要）
    port = int(os.environ.get('PORT', 8080))

    print(f"📡 服务器地址: http://localhost:{port}")
    print("💡 在浏览器中打开上述地址即可使用")
    print("🔥 支持同时监控多个直播间")
    print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
