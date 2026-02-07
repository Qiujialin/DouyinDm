# 抖音弹幕实时监控 Web 应用

## 🚀 快速启动

```bash
# 方法 1：使用启动脚本
./run.sh

# 方法 2：直接启动
python3 web_server.py
```

然后在浏览器中打开：**http://localhost:8080**

---

## 📦 安装依赖

```bash
python3 -m pip install flask flask-socketio flask-cors simple-websocket websocket-client pyexecjs protobuf --break-system-packages
```

---

## 📖 使用说明

1. **启动服务器**：`python3 web_server.py`
2. **打开浏览器**：访问 `http://localhost:8080`
3. **输入直播间 ID**：例如 `4253196531`
4. **设置过滤（可选）**：例如 `礼物|关注`
5. **点击"启动监控"**：开始接收弹幕
6. **复制弹幕**：点击"复制"按钮

---

## ✨ 功能特性

- ✅ 自动爬取直播间聊天弹幕
- ✅ 支持正则表达式过滤
- ✅ 网页实时显示最新20条
- ✅ 每条带一个复制按钮
- ✅ 只显示消息内容，不显示发送人
- ✅ 美观的现代化界面

---

## 💡 正则表达式示例

### 基础过滤

| 过滤规则 | 说明 |
|---------|------|
| `礼物` | 只显示包含"礼物"的弹幕 |
| `礼物\|关注` | 只显示包含"礼物"或"关注"的弹幕 |
| `^\d+$` | 只显示纯数字弹幕 |
| 留空 | 显示所有弹幕 |

### 王者荣耀口令过滤（价格 ≥ 900）

```regex
王者荣耀【[^】]+】.*?今天(9[0-9]{2}|[1-9]\d{3,})块
```

**示例弹幕：**
- ✅ 王者荣耀【修罗HR19EZ】我的小马糕今天**989**块 - 匹配
- ❌ 王者荣耀【千年之狐6JS7JC】我的小马糕今天**673**块 - 不匹配
- ✅ 王者荣耀【测试ABCDEF】我的小马糕今天**1000**块 - 匹配

---

## 📁 项目文件

### 核心文件（必需）

```
DouyinDm/
├── web_server.py              # Flask 后端服务器
├── templates/
│   └── index.html             # 前端页面
├── douyin_danmaku.py          # 弹幕接收器
├── get_real_room_id.py        # 获取真实 room_id
├── douyin_sign.py             # 签名计算
├── douyin_pb2.py              # Protobuf 消息定义
└── douyin_sdk.js              # JavaScript SDK
```

### 辅助文件（可选）

```
├── debug_danmaku.py           # 调试版本
├── run.sh                     # 启动脚本
└── README.md                  # 本文档
```

---

## 🔧 配置

### 修改端口

编辑 `web_server.py` 最后一行：

```python
socketio.run(app, host='0.0.0.0', port=8080, ...)
#                                      ^^^^
#                                      改成你想要的端口
```

### 修改显示数量

编辑 `templates/index.html`：

```javascript
const maxDanmaku = 20;  // 改成你想要的数量
```

---

## 🐛 常见问题

### Q: 启动后没有弹幕？

**A:** 检查：
1. 直播间是否正在直播
2. 直播间 ID 是否正确
3. 网络连接是否正常

### Q: 端口被占用？

**A:** 修改 `web_server.py` 中的端口号

### Q: 正则表达式不生效？

**A:** 确保正则表达式语法正确，在启动前设置过滤器

---

## 📄 许可证

本项目基于 pure_live 项目实现，仅供学习和研究使用。

---

**最后更新**: 2026-02-08
