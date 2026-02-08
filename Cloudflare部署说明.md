# Cloudflare Pages 部署指南 - 浏览器版

## 📋 版本说明

这是**纯前端浏览器版本**，与后端版本的区别：

| 特性 | 后端版本 (Railway) | 浏览器版本 (Cloudflare) |
|------|-------------------|------------------------|
| 部署平台 | Railway/服务器 | Cloudflare Pages |
| 技术栈 | Python + Flask | 纯 HTML/CSS/JS |
| 弹幕获取 | 服务器连接抖音 | 浏览器直接连接 |
| 登录要求 | 无需登录 | 需要浏览器登录抖音 |
| CORS 限制 | 无 | 有（需要扩展或代理） |
| 成本 | $5/月起 | 完全免费 |

## ⚠️ 重要限制

### 浏览器版本的限制

由于浏览器安全策略（CORS），**纯前端版本无法直接连接抖音 WebSocket**。

**当前状态：**
- ✅ 界面完整可用
- ✅ 配置保存到 localStorage
- ✅ 过滤器功能完整
- ❌ 无法直接获取弹幕（CORS 限制）

### 解决方案

#### 方案1：使用后端版本（推荐）
部署到 Railway，无任何限制：
- 参考 `Railway部署指南.md`
- 完整功能，无需浏览器登录

#### 方案2：使用浏览器扩展
安装 CORS 解除扩展：
- Chrome: "CORS Unblock" 或 "Allow CORS"
- Firefox: "CORS Everywhere"
- ⚠️ 仅用于个人测试，有安全风险

#### 方案3：开发浏览器扩展版本
将此页面打包为浏览器扩展：
- 扩展可以绕过 CORS 限制
- 需要额外开发工作

## 🚀 部署到 Cloudflare Pages

### 步骤1：准备文件

创建项目结构：
```
douyin-browser/
├── index.html (重命名 index_browser.html)
└── _headers (可选，配置 CORS)
```

### 步骤2：推送到 GitHub

```bash
cd /path/to/douyin-browser
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/douyin-browser.git
git push -u origin main
```

### 步骤3：连接 Cloudflare Pages

1. 访问 https://dash.cloudflare.com
2. 选择 "Pages" → "Create a project"
3. 连接 GitHub 仓库
4. 配置构建设置：
   - **Framework preset**: None
   - **Build command**: (留空)
   - **Build output directory**: `/`
5. 点击 "Save and Deploy"

### 步骤4：访问部署

部署完成后，Cloudflare 会提供域名：
- 格式：`https://douyin-browser.pages.dev`
- 可以绑定自定义域名

## 📝 使用说明

### 1. 准备工作

在使用前，需要在浏览器中登录抖音：
1. 打开新标签页访问 https://live.douyin.com
2. 登录你的抖音账号
3. 保持标签页打开

### 2. 添加直播间

- 输入直播间链接：`https://live.douyin.com/123456`
- 或直接输入 Web RID：`123456`

### 3. 设置过滤器

- 支持正则表达式
- 例如：`王者荣耀.*今天.*块`

### 4. 数据持久化

- 配置自动保存到浏览器 localStorage
- 刷新页面后自动恢复

## 🔧 本地测试

直接在浏览器中打开 `index_browser.html` 即可测试。

## ⚡ 性能优化

### 启用 Cloudflare 加速

在 Cloudflare Pages 设置中：
1. 启用 "Auto Minify" (HTML/CSS/JS)
2. 启用 "Brotli" 压缩
3. 配置缓存规则

### 添加 PWA 支持（可选）

创建 `manifest.json` 和 Service Worker，使其可以离线使用。

## 📊 成本对比

| 平台 | 成本 | 功能完整度 | 推荐度 |
|------|------|-----------|--------|
| Cloudflare Pages | 免费 | 受限（CORS） | ⭐⭐⭐ |
| Railway | $5/月 | 完整 | ⭐⭐⭐⭐⭐ |

## 🎯 推荐方案

### 个人使用
- **推荐**：Railway 后端版本
- **原因**：功能完整，无需浏览器登录

### 演示/展示
- **推荐**：Cloudflare Pages 浏览器版
- **原因**：免费，快速部署

### 生产环境
- **推荐**：自建服务器或 Railway
- **原因**：稳定可靠，无限制

## 📖 总结

**浏览器版本适合：**
- ✅ 快速演示界面
- ✅ 学习前端技术
- ✅ 零成本部署

**浏览器版本不适合：**
- ❌ 实际使用（CORS 限制）
- ❌ 生产环境
- ❌ 多用户场景

**建议：**
如果需要实际使用，请部署后端版本到 Railway（已成功部署）。浏览器版本仅作为备选方案或学习参考。
