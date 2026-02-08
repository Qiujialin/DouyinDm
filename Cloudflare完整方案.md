# 抖音弹幕监控 - Cloudflare 完整方案

## 🎯 核心思路

参考 MoonTV 项目，使用 **Cloudflare Workers 作为代理**来绕过浏览器 CORS 限制。

## 📋 架构设计

```
用户浏览器 → Cloudflare Pages (前端)
              ↓
         Cloudflare Workers (代理)
              ↓
         抖音 WebSocket 服务器
```

## 🚀 实现方案

### 方案1：Cloudflare Workers + Pages（推荐）

#### 组件说明

1. **Cloudflare Pages**
   - 托管纯静态前端页面
   - 提供用户界面
   - 管理配置（localStorage）

2. **Cloudflare Workers**
   - 作为 WebSocket 代理
   - 绕过 CORS 限制
   - 转发抖音弹幕数据

#### 部署步骤

**步骤1：创建 Worker 代理**

创建文件 `douyin-proxy.worker.js`：

```javascript
// Cloudflare Worker - 抖音 WebSocket 代理
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)

  // 处理 WebSocket 升级请求
  if (request.headers.get('Upgrade') === 'websocket') {
    return handleWebSocket(request)
  }

  // 处理普通 HTTP 请求（代理抖音 API）
  return handleHttpProxy(request)
}

async function handleWebSocket(request) {
  const url = new URL(request.url)
  const targetUrl = url.searchParams.get('target')

  if (!targetUrl) {
    return new Response('Missing target URL', { status: 400 })
  }

  // 创建 WebSocket 连接到抖音服务器
  const [client, server] = Object.values(new WebSocketPair())

  // 连接到目标 WebSocket
  const targetWs = new WebSocket(targetUrl)

  // 转发消息：客户端 → 抖音
  client.addEventListener('message', event => {
    targetWs.send(event.data)
  })

  // 转发消息：抖音 → 客户端
  targetWs.addEventListener('message', event => {
    client.send(event.data)
  })

  // 处理连接关闭
  targetWs.addEventListener('close', () => {
    client.close()
  })

  client.addEventListener('close', () => {
    targetWs.close()
  })

  return new Response(null, {
    status: 101,
    webSocket: server,
  })
}

async function handleHttpProxy(request) {
  const url = new URL(request.url)
  const targetUrl = decodeURIComponent(url.pathname.replace('/', ''))

  if (!targetUrl) {
    return new Response('Douyin Proxy Worker', {
      headers: { 'Content-Type': 'text/plain' }
    })
  }

  // 代理 HTTP 请求
  const response = await fetch(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body
  })

  // 添加 CORS 头
  const newResponse = new Response(response.body, response)
  newResponse.headers.set('Access-Control-Allow-Origin', '*')
  newResponse.headers.set('Access-Control-Allow-Methods', '*')
  newResponse.headers.set('Access-Control-Allow-Headers', '*')

  return newResponse
}
```

**步骤2：部署 Worker**

```bash
# 安装 Wrangler CLI
npm install -g wrangler

# 登录 Cloudflare
wrangler login

# 创建 Worker
wrangler init douyin-proxy

# 复制 worker 代码到 src/index.js

# 部署
wrangler deploy
```

**步骤3：创建前端页面**

修改之前的 `index_browser.html`，使用 Worker 代理：

```javascript
// 连接 WebSocket（通过 Worker 代理）
function connectWebSocket(roomId) {
  const workerUrl = 'wss://douyin-proxy.你的用户名.workers.dev'
  const targetUrl = `wss://webcast3-ws-web-lq.douyin.com/webcast/im/push/v2/`

  const ws = new WebSocket(`${workerUrl}?target=${encodeURIComponent(targetUrl)}`)

  ws.onmessage = (event) => {
    // 处理弹幕数据
    handleDanmaku(event.data)
  }

  return ws
}
```

**步骤4：部署到 Cloudflare Pages**

```bash
# 推送到 GitHub
git add .
git commit -m "Add Cloudflare version"
git push

# 在 Cloudflare Pages 创建项目
# 连接 GitHub 仓库
# 构建设置：无需构建命令
# 输出目录：/
```

### 方案2：纯 Cloudflare Workers（更简单）

将前端和代理合并到一个 Worker：

```javascript
// 完整的 Worker 代码
export default {
  async fetch(request, env) {
    const url = new URL(request.url)

    // 返回前端页面
    if (url.pathname === '/') {
      return new Response(getHtmlPage(), {
        headers: { 'Content-Type': 'text/html' }
      })
    }

    // WebSocket 代理
    if (url.pathname === '/ws') {
      return handleWebSocket(request)
    }

    // HTTP 代理
    return handleHttpProxy(request)
  }
}

function getHtmlPage() {
  return `<!DOCTYPE html>
<html>
<head>
  <title>抖音弹幕监控</title>
  <!-- 完整的 HTML 代码 -->
</head>
<body>
  <!-- UI 界面 -->
  <script>
    // 使用相对路径连接 WebSocket
    const ws = new WebSocket('wss://' + location.host + '/ws?room=123456')
  </script>
</body>
</html>`
}
```

## ⚠️ 重要限制

### Cloudflare Workers 限制

1. **CPU 时间限制**
   - 免费版：10ms
   - 付费版：50ms
   - 可能不足以处理复杂的 WebSocket 消息

2. **WebSocket 连接限制**
   - 免费版：有限制
   - 需要付费计划才能稳定使用

3. **请求数限制**
   - 免费版：100,000 请求/天
   - 超出需要付费

### 技术难点

1. **抖音 WebSocket 协议复杂**
   - 需要签名验证
   - 需要 Cookie
   - 消息格式为 Protobuf

2. **Worker 环境限制**
   - 不支持某些 Node.js 库
   - 需要重写部分逻辑

## 💡 最终建议

### 对比分析

| 方案 | 成本 | 难度 | 稳定性 | 推荐度 |
|------|------|------|--------|--------|
| Railway 后端 | $5/月 | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| CF Workers | 免费/付费 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 纯浏览器 | 免费 | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |

### 推荐方案

**继续使用 Railway 后端版本**

原因：
1. ✅ 已经部署成功
2. ✅ 功能完整稳定
3. ✅ 成本可控（$5/月）
4. ✅ 无技术限制
5. ✅ 维护简单

**Cloudflare 方案的问题：**
1. ❌ 需要大量开发工作
2. ❌ Worker 限制多
3. ❌ 抖音协议复杂
4. ❌ 稳定性未知
5. ❌ 可能需要付费才能稳定运行

## 🎯 结论

虽然 MoonTV 的 Cloudflare 方案很优雅，但它适用于：
- 简单的 HTTP 代理
- 视频流转发
- 静态内容

**不适用于：**
- 复杂的 WebSocket 长连接
- 需要持续处理的实时数据
- 有状态的连接管理

**建议：**
回到 Railway，配置好域名，开始使用！这是最稳定、最简单的方案。
