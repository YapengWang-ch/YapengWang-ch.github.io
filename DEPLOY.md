# YapengWang-ch.github.io - 留言板服务器部署指南

## 项目结构

```
YapengWang-ch.github.io/
├── index.html          # 主页（简历）
├── notes.html          # 个人笔记
├── guestbook.html      # 留言板（前端）
├── server.py           # 留言板 Flask API 服务器
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 镜像构建文件
├── docker-compose.yml  # Docker Compose 部署配置
└── data/
    └── messages.json   # 留言数据文件（自动生成）
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/messages?page=1&per_page=5` | 获取留言列表（分页） |
| POST | `/api/messages` | 创建新留言 |
| DELETE | `/api/messages/<id>` | 删除留言（需密钥） |
| GET | `/api/health` | 健康检查 |

## 部署方式

### 方式一：直接运行（开发/测试）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务器
python server.py

# 服务器默认运行在 http://0.0.0.0:5000
```

设置环境变量：
- `PORT`：服务器端口（默认 5000）
- `ADMIN_KEY`：删除留言的管理员密钥（默认 `admin123`）
- `FLASK_DEBUG=1`：开启调试模式

### 方式二：Docker 部署（推荐）

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 方式三：Gunicorn 生产部署

```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 30 server:app
```

## 前端配置

在 `guestbook.html` 中修改 API 地址。可以通过以下两种方式：

1. **直接修改 JS 中的 `API_BASE`**：
   ```javascript
   const API_BASE = 'https://your-server.com:5000';
   ```

2. **在 HTML 中通过全局变量设置**（在 `<script>` 标签之前添加）：
   ```html
   <script>window.GUESTBOOK_API_BASE = 'https://your-server.com:5000';</script>
   ```

## 静态文件托管

HTML 页面（`index.html`、`notes.html`、`guestbook.html`）可以：
- 通过 GitHub Pages 托管（免费）
- 通过 Nginx 托管
- 通过 Flask 的静态文件服务托管

如果使用 Nginx 反向代理，示例配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 静态页面
    root /path/to/YapengWang-ch.github.io;
    index index.html;

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 安全建议

1. 部署时修改默认的 `ADMIN_KEY`
2. 生产环境使用 HTTPS
3. 考虑添加速率限制防止刷留言
4. 定期备份 `data/messages.json`
