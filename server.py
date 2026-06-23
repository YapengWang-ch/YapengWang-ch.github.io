"""
Yapeng 个人网站 - 留言板后端 API
Flask 服务器，留言数据存储在服务器端 JSON 文件中
"""
import json
import os
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=None)  # 手动控制静态文件
CORS(app)  # 允许跨域请求

# 网站根目录（HTML 文件所在目录）
SITE_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages.json")
MAX_MSG_LENGTH = 1000
MAX_NAME_LENGTH = 30
MAX_EMAIL_LENGTH = 100


def load_messages():
    """从 JSON 文件加载留言"""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_messages(messages):
    """保存留言到 JSON 文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


@app.route("/api/messages", methods=["GET"])
def get_messages():
    """获取留言列表，支持分页"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 5, type=int)

    # 限制每页最大数量
    per_page = min(per_page, 50)

    messages = load_messages()

    # 按时间倒序排列
    messages.sort(key=lambda m: m.get("time", 0), reverse=True)

    total = len(messages)
    total_pages = max(1, (total + per_page - 1) // per_page)

    start = (page - 1) * per_page
    end = start + per_page
    page_messages = messages[start:end]

    return jsonify({
        "success": True,
        "data": {
            "messages": page_messages,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
    })


@app.route("/api/messages", methods=["POST"])
def create_message():
    """创建新留言"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    content = (data.get("content") or "").strip()

    # 验证
    errors = []
    if not name:
        errors.append("昵称不能为空")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"昵称不能超过 {MAX_NAME_LENGTH} 个字符")

    if not content:
        errors.append("留言内容不能为空")
    elif len(content) > MAX_MSG_LENGTH:
        errors.append(f"留言内容不能超过 {MAX_MSG_LENGTH} 个字符")

    if email and len(email) > MAX_EMAIL_LENGTH:
        errors.append(f"邮箱不能超过 {MAX_EMAIL_LENGTH} 个字符")

    if errors:
        return jsonify({"success": False, "error": "; ".join(errors)}), 400

    # 简易 XSS 防护：移除 HTML 标签
    import re
    name = re.sub(r"<[^>]*>", "", name)
    content = re.sub(r"<[^>]*>", "", content)

    message = {
        "id": int(time.time() * 1000),
        "name": name,
        "email": email,
        "content": content,
        "time": int(time.time() * 1000),
        "ip": request.remote_addr or "unknown"
    }

    messages = load_messages()
    messages.append(message)
    save_messages(messages)

    return jsonify({
        "success": True,
        "data": {"message": message}
    }), 201


@app.route("/api/messages/<int:msg_id>", methods=["DELETE"])
def delete_message(msg_id):
    """删除留言（需要提供删除密钥）"""
    data = request.get_json(silent=True) or {}
    delete_key = (data.get("delete_key") or "").strip()

    # 简单的删除密钥验证（可在部署时修改）
    ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin123")

    if delete_key != ADMIN_KEY:
        return jsonify({"success": False, "error": "删除密钥无效"}), 403

    messages = load_messages()
    original_len = len(messages)
    messages = [m for m in messages if m.get("id") != msg_id]

    if len(messages) == original_len:
        return jsonify({"success": False, "error": "留言不存在"}), 404

    save_messages(messages)
    return jsonify({"success": True, "data": {"deleted_id": msg_id}})


@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查接口"""
    msg_count = len(load_messages())
    return jsonify({
        "success": True,
        "data": {
            "status": "ok",
            "message_count": msg_count,
            "server_time": datetime.now().isoformat()
        }
    })


# ═══════════ 静态文件服务 ═══════════
@app.route("/")
def index():
    """主页"""
    return send_from_directory(SITE_ROOT, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """提供静态文件（HTML, CSS, JS 等）"""
    # 只允许安全的文件类型
    safe_extensions = {".html", ".css", ".js", ".json", ".txt", ".xml", ".ico", ".png", ".jpg", ".svg"}
    _, ext = os.path.splitext(filename)
    if ext.lower() not in safe_extensions:
        return jsonify({"success": False, "error": "不支持的文件类型"}), 403

    file_path = os.path.join(SITE_ROOT, filename)
    # 防止路径穿越攻击
    if not os.path.realpath(file_path).startswith(os.path.realpath(SITE_ROOT)):
        return jsonify({"success": False, "error": "禁止访问"}), 403

    if not os.path.isfile(file_path):
        return jsonify({"success": False, "error": "文件不存在"}), 404

    return send_from_directory(SITE_ROOT, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"🚀 留言板 API 服务器启动: http://0.0.0.0:{port}")
    print(f"   📄 主页: http://localhost:{port}/")
    print(f"   📝 笔记: http://localhost:{port}/notes.html")
    print(f"   💬 留言: http://localhost:{port}/guestbook.html")
    app.run(host="0.0.0.0", port=port, debug=debug)
