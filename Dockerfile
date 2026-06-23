# Yapeng 个人网站 - Docker 部署配置
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY server.py .
COPY index.html notes.html guestbook.html ./static/

# 创建数据目录
RUN mkdir -p /app/data
ENV DATA_FILE=/app/data/messages.json

EXPOSE 5000

# 使用 gunicorn 运行生产服务器
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "server:app"]
