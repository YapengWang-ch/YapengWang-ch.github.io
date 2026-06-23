"""
Yapeng 个人网站 - 留言板后端 API
Flask 服务器，留言数据存储在服务器端 JSON 文件中
"""
import hashlib
import json
import os
import secrets
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=None)  # 手动控制静态文件
CORS(app)  # 允许跨域请求

# 网站根目录（HTML 文件所在目录）
SITE_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(SITE_ROOT, "messages.json")
USERS_FILE = os.path.join(SITE_ROOT, "users.json")
NOTES_DIR = os.path.join(SITE_ROOT, "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

MAX_MSG_LENGTH = 1000
MAX_NAME_LENGTH = 30
MAX_EMAIL_LENGTH = 100
MAX_NOTE_TITLE_LENGTH = 120
MAX_NOTE_FILE_SIZE = 200 * 1024  # 200 KB
MAX_USERNAME_LENGTH = 30
MIN_PASSWORD_LENGTH = 4


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


# ═══════════ 用户系统 ═══════════

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$", 1)
    if len(parts) != 2:
        return False
    salt, h = parts
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def find_user_by_token(token: str):
    users = load_users()
    for username, info in users.items():
        if info.get("token") == token:
            return username, info
    return None, None


@app.route("/api/users/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "用户名和密码不能为空"}), 400
    if len(username) > MAX_USERNAME_LENGTH:
        return jsonify({"success": False, "error": f"用户名不能超过 {MAX_USERNAME_LENGTH} 个字符"}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"success": False, "error": f"密码至少 {MIN_PASSWORD_LENGTH} 个字符"}), 400

    users = load_users()
    if username in users:
        return jsonify({"success": False, "error": "用户名已存在"}), 409

    token = secrets.token_hex(16)
    users[username] = {
        "password": hash_password(password),
        "token": token,
        "display_name": username,
        "bio": "",
        "privacy": "public",
        "created_at": int(time.time() * 1000)
    }
    save_users(users)

    return jsonify({
        "success": True,
        "data": {"username": username, "token": token}
    }), 201


@app.route("/api/users/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    users = load_users()
    if username not in users:
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401

    if not verify_password(password, users[username]["password"]):
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401

    token = secrets.token_hex(16)
    users[username]["token"] = token
    save_users(users)

    return jsonify({
        "success": True,
        "data": {"username": username, "token": token}
    })


@app.route("/api/users/logout", methods=["POST"])
def logout_user():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"success": False, "error": "缺少 token"}), 400

    username, _ = find_user_by_token(token)
    if not username:
        return jsonify({"success": False, "error": "无效的 token"}), 401

    users = load_users()
    if username in users:
        users[username].pop("token", None)
        save_users(users)

    return jsonify({"success": True})


@app.route("/api/users/me", methods=["GET"])
def get_current_user():
    token = request.args.get("token", "").strip()
    if not token:
        return jsonify({"success": False, "error": "缺少 token"}), 400

    username, _ = find_user_by_token(token)
    if not username:
        return jsonify({"success": False, "error": "无效的 token"}), 401

    users = load_users()
    user_info = users.get(username, {})
    return jsonify({
        "success": True,
        "data": {
            "username": username,
            "display_name": user_info.get("display_name", username),
            "bio": user_info.get("bio", ""),
            "privacy": user_info.get("privacy", "public")
        }
    })


@app.route("/api/profile/<username>", methods=["GET"])
def get_profile(username):
    """获取用户主页。privacy=private 时仅返回有限信息。"""
    users = load_users()
    if username not in users:
        return jsonify({"success": False, "error": "用户不存在"}), 404

    info = users[username]
    is_private = info.get("privacy", "public") == "private"
    author_notes = [
        f for f, a in _load_note_authors().items() if a == username
    ]

    if is_private:
        return jsonify({
            "success": True,
            "data": {
                "username": username,
                "display_name": info.get("display_name", username),
                "privacy": "private"
            }
        })

    return jsonify({
        "success": True,
        "data": {
            "username": username,
            "display_name": info.get("display_name", username),
            "bio": info.get("bio", ""),
            "privacy": "public",
            "notes_count": len(author_notes),
            "created_at": info.get("created_at", 0)
        }
    })


@app.route("/api/profile", methods=["PUT"])
def update_profile():
    """修改个人信息，需 token。"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    token = (data.get("token") or "").strip()
    username, _ = find_user_by_token(token)
    if not username:
        return jsonify({"success": False, "error": "无效的 token，请重新登录"}), 401

    users = load_users()
    user_info = users.get(username, {})

    display_name = data.get("display_name")
    bio = data.get("bio")
    privacy = data.get("privacy")

    if display_name is not None:
        display_name = display_name.strip()
        if display_name and len(display_name) > 50:
            return jsonify({"success": False, "error": "显示名称不能超过 50 个字符"}), 400
        user_info["display_name"] = display_name or username

    if bio is not None:
        bio = bio.strip()
        if len(bio) > 500:
            return jsonify({"success": False, "error": "个人简介不能超过 500 个字符"}), 400
        user_info["bio"] = bio

    if privacy is not None:
        if privacy not in ("public", "private"):
            return jsonify({"success": False, "error": "privacy 必须为 public 或 private"}), 400
        user_info["privacy"] = privacy

    users[username] = user_info
    save_users(users)

    return jsonify({
        "success": True,
        "data": {
            "username": username,
            "display_name": user_info.get("display_name", username),
            "bio": user_info.get("bio", ""),
            "privacy": user_info.get("privacy", "public")
        }
    })


def sanitize_note_filename(name: str) -> str:
    """生成安全的 Markdown 文件名。"""
    import re
    base = name.strip()
    if not base:
        base = f"note-{int(time.time())}"
    base = base.replace(" ", "-")
    base = re.sub(r"[^\w\-.]+", "", base, flags=re.UNICODE)
    if not base.lower().endswith(".md"):
        base += ".md"
    return base[:255]


def load_notes():
    """列出 notes 目录下的 Markdown 笔记。"""
    notes = []
    authors = _load_note_authors()
    for filename in os.listdir(NOTES_DIR):
        if not filename.lower().endswith(".md"):
            continue
        file_path = os.path.join(NOTES_DIR, filename)
        if not os.path.isfile(file_path):
            continue
        title = os.path.splitext(filename)[0].replace("-", " ").strip()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("# "):
                    title = first_line[2:].strip() or title
        except IOError:
            pass
        created_at = int(os.path.getmtime(file_path) * 1000)
        notes.append({
            "id": filename,
            "filename": filename,
            "title": title,
            "author": authors.get(filename, ""),
            "created_at": created_at
        })
    notes.sort(key=lambda n: n["created_at"], reverse=True)
    return notes


def _load_note_authors():
    author_file = os.path.join(NOTES_DIR, ".authors.json")
    if not os.path.exists(author_file):
        return {}
    try:
        with open(author_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_note_author(filename, author):
    author_file = os.path.join(NOTES_DIR, ".authors.json")
    authors = _load_note_authors()
    authors[filename] = author
    with open(author_file, "w", encoding="utf-8") as f:
        json.dump(authors, f, ensure_ascii=False, indent=2)


def safe_note_path(note_name: str) -> str:
    normalized = os.path.normpath(note_name)
    if normalized.startswith("..") or os.path.isabs(normalized):
        raise ValueError("非法文件名")
    file_path = os.path.join(NOTES_DIR, normalized)
    if not os.path.realpath(file_path).startswith(os.path.realpath(NOTES_DIR)):
        raise ValueError("非法文件名")
    return file_path


@app.route("/api/notes", methods=["GET"])
def get_notes():
    """列出所有 Markdown 笔记。"""
    return jsonify({"success": True, "data": {"notes": load_notes()}})


@app.route("/api/notes/<path:note_name>", methods=["GET"])
def get_note_content(note_name):
    """获取单篇笔记的 Markdown 内容。"""
    try:
        file_path = safe_note_path(note_name)
    except ValueError:
        return jsonify({"success": False, "error": "非法文件名"}), 403

    if not os.path.isfile(file_path):
        return jsonify({"success": False, "error": "笔记不存在"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError:
        return jsonify({"success": False, "error": "读取笔记失败"}), 500

    return jsonify({"success": True, "data": {"filename": note_name, "content": content}})


@app.route("/api/notes", methods=["POST"])
def create_note():
    """上传 Markdown 笔记，需提供 token 或 upload_key。"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    upload_key = (data.get("upload_key") or "").strip()
    token = (data.get("token") or "").strip()
    filename_hint = (data.get("filename") or "").strip()

    author = ""
    if token:
        username, _ = find_user_by_token(token)
        if not username:
            return jsonify({"success": False, "error": "无效的 token，请重新登录"}), 401
        author = username
    else:
        NOTE_UPLOAD_KEY = os.environ.get("NOTE_UPLOAD_KEY", "note123")
        if upload_key != NOTE_UPLOAD_KEY:
            return jsonify({"success": False, "error": "请先登录或提供上传密码"}), 403

    if not title:
        return jsonify({"success": False, "error": "笔记标题不能为空"}), 400
    if not content:
        return jsonify({"success": False, "error": "笔记内容不能为空"}), 400
    if len(title) > MAX_NOTE_TITLE_LENGTH:
        return jsonify({"success": False, "error": f"笔记标题不能超过 {MAX_NOTE_TITLE_LENGTH} 个字符"}), 400
    if len(content.encode("utf-8")) > MAX_NOTE_FILE_SIZE:
        return jsonify({"success": False, "error": "笔记内容超过大小限制"}), 400

    filename = filename_hint or title
    filename = sanitize_note_filename(filename)
    file_path = os.path.join(NOTES_DIR, filename)
    if os.path.exists(file_path):
        base, ext = os.path.splitext(filename)
        suffix = 1
        while os.path.exists(os.path.join(NOTES_DIR, f"{base}-{suffix}{ext}")):
            suffix += 1
        filename = f"{base}-{suffix}{ext}"
        file_path = os.path.join(NOTES_DIR, filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except IOError:
        return jsonify({"success": False, "error": "写入笔记失败"}), 500

    if author:
        _save_note_author(filename, author)

    return jsonify({
        "success": True,
        "data": {
            "filename": filename,
            "title": title,
            "author": author,
            "created_at": int(time.time() * 1000)
        }
    }), 201


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
