from flask import Flask, request, render_template_string, jsonify, Response, session
import requests
import time
import threading
import uuid
import datetime
from collections import deque
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'  # Required for session

# Global task storage: task_id -> task_info dict
tasks = {}
# For live log streaming: task_id -> deque of log lines
task_logs = {}

# Server start time for uptime tracking
SERVER_START_TIME = datetime.datetime.now()

HEADERS = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'www.google.com'
}

# ---------- Helper Functions ----------
def add_log(task_id, level, message):
    """Add a log entry for a specific task."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'level': level,
        'message': message
    }
    if task_id not in task_logs:
        task_logs[task_id] = deque(maxlen=500)
    task_logs[task_id].append(log_entry)

def stop_task(task_id, requester_id):
    """
    Stop a running task safely with ownership check.
    Returns: (success, message, http_status_code)
    """
    # Check if task exists
    if task_id not in tasks:
        return False, f"Task {task_id} not found", 404
    
    task_info = tasks[task_id]
    
    # Check if task is already stopped
    if not task_info.get('active', False):
        return False, f"Task {task_id} is already stopped", 400
    
    # Check ownership
    if task_info.get('owner_id') != requester_id:
        return False, "Unauthorized: You don't own this task", 403
    
    # Stop the task
    task_info['stop_flag'] = True
    add_log(task_id, 'INFO', f"Task stopped by owner {requester_id}")
    return True, f"Task {task_id} stopped successfully", 200

def message_sender(task_id, owner_id, thread_id, access_tokens, messages, haters_name, speed):
    """Background function to send messages."""
    add_log(task_id, 'INFO', f"Task started by {owner_id}. Target: {thread_id}, Hater: {haters_name}, Speed: {speed}s")
    
    num_comments = len(messages)
    max_tokens = len(access_tokens)
    post_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
    
    sent_count = 0
    failed_count = 0
    message_index = 0
    
    while not tasks.get(task_id, {}).get('stop_flag', False):
        try:
            token_index = message_index % max_tokens
            access_token = access_tokens[token_index]
            message = messages[message_index % num_comments].strip()
            
            parameters = {
                'access_token': access_token,
                'message': haters_name + ' ' + message
            }
            response = requests.post(post_url, json=parameters, headers=HEADERS)
            
            current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
            
            if response.ok:
                sent_count += 1
                log_msg = f"[✓] Msg #{sent_count} | Token #{token_index+1} | {haters_name} {message}"
                add_log(task_id, 'SUCCESS', log_msg)
            else:
                failed_count += 1
                log_msg = f"[✗] Failed | Token #{token_index+1} | {haters_name} {message} | HTTP {response.status_code}"
                add_log(task_id, 'ERROR', log_msg)
            
            # Update task stats
            if task_id in tasks:
                tasks[task_id]['stats'] = {
                    'sent': sent_count,
                    'failed': failed_count,
                    'last_message': haters_name + ' ' + message,
                    'last_update': current_time
                }
            
            message_index += 1
            time.sleep(speed)
            
        except Exception as e:
            add_log(task_id, 'ERROR', f"Exception: {str(e)}")
            time.sleep(30)
    
    # Task finished
    add_log(task_id, 'INFO', f"Task stopped. Total sent: {sent_count}, Failed: {failed_count}")
    if task_id in tasks:
        tasks[task_id]['active'] = False
        tasks[task_id]['stop_flag'] = False

# ---------- Routes ----------
@app.route('/')
def index():
    uptime_seconds = (datetime.datetime.now() - SERVER_START_TIME).total_seconds()
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
    
    # Get current user from session or create new one
    if 'user_id' not in session:
        session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
    
    return render_template_string(HTML_TEMPLATE, uptime=uptime_str, tasks=tasks, current_user=session['user_id'])

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks with optional filter by owner."""
    requester_id = session.get('user_id')
    if not requester_id:
        return jsonify({'error': 'No user session'}), 401
    
    # Return only tasks that belong to the requester (for security)
    user_tasks = {}
    for tid, info in tasks.items():
        if info.get('owner_id') == requester_id:
            user_tasks[tid] = {
                'id': tid,
                'thread_id': info['thread_id'],
                'haters_name': info['haters_name'],
                'active': info.get('active', False),
                'stats': info.get('stats', {}),
                'created_at': info.get('created_at'),
                'owner_id': info.get('owner_id')
            }
    return jsonify(user_tasks)

@app.route('/api/tasks/all', methods=['GET'])
def get_all_tasks_admin():
    """Admin endpoint to see all tasks (optional, for debugging)."""
    # In production, add admin authentication here
    all_tasks = {}
    for tid, info in tasks.items():
        all_tasks[tid] = {
            'id': tid,
            'owner_id': info.get('owner_id'),
            'active': info.get('active', False),
            'created_at': info.get('created_at')
        }
    return jsonify(all_tasks)

@app.route('/api/tasks/start', methods=['POST'])
def start_task():
    """Start a new messaging task."""
    try:
        requester_id = session.get('user_id')
        if not requester_id:
            # Create new user session
            requester_id = f"user_{uuid.uuid4().hex[:8]}"
            session['user_id'] = requester_id
        
        thread_id = request.form.get('threadId')
        haters_name = request.form.get('kidx')
        time_interval = int(request.form.get('time'))
        
        txt_file = request.files.get('txtFile')
        if not txt_file:
            return jsonify({'error': 'No token file provided'}), 400
        access_tokens = txt_file.read().decode().splitlines()
        
        messages_file = request.files.get('messagesFile')
        if not messages_file:
            return jsonify({'error': 'No messages file provided'}), 400
        messages = messages_file.read().decode().splitlines()
        
        if not thread_id or not access_tokens or not messages or not haters_name:
            return jsonify({'error': 'Missing required fields'}), 400
        
        task_id = str(uuid.uuid4())[:8]
        
        # Store task info with owner
        tasks[task_id] = {
            'id': task_id,
            'owner_id': requester_id,
            'thread_id': thread_id,
            'haters_name': haters_name,
            'speed': time_interval,
            'active': True,
            'stop_flag': False,
            'created_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'stats': {
                'sent': 0,
                'failed': 0,
                'last_message': '',
                'last_update': ''
            }
        }
        
        # Start background thread
        thread = threading.Thread(
            target=message_sender,
            args=(task_id, requester_id, thread_id, access_tokens, messages, haters_name, time_interval),
            daemon=True
        )
        tasks[task_id]['thread'] = thread
        thread.start()
        
        return jsonify({
            'status': 'started', 
            'task_id': task_id,
            'owner_id': requester_id,
            'message': f'Task {task_id} started successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/stop', methods=['POST'])
def stop_task_route():
    """Stop a specific task by ID with ownership verification."""
    data = request.get_json()
    task_id = data.get('task_id')
    requester_id = session.get('user_id')
    
    if not task_id:
        return jsonify({'error': 'No task_id provided'}), 400
    
    if not requester_id:
        return jsonify({'error': 'No user session found'}), 401
    
    success, message, status_code = stop_task(task_id, requester_id)
    
    return jsonify({
        'success': success,
        'message': message,
        'task_id': task_id,
        'requester_id': requester_id
    }), status_code

@app.route('/api/tasks/<task_id>/logs')
def task_logs_view(task_id):
    """Get logs for a specific task (only if owner)."""
    requester_id = session.get('user_id')
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check ownership
    if tasks[task_id].get('owner_id') != requester_id:
        return jsonify({'error': 'Unauthorized: You don\'t own this task'}), 403
    
    if task_id not in task_logs:
        return jsonify([])
    return jsonify(list(task_logs[task_id]))

@app.route('/api/tasks/<task_id>/live')
def live_logs_stream(task_id):
    """Server-sent events endpoint for live logs with ownership check."""
    requester_id = session.get('user_id')
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    if tasks[task_id].get('owner_id') != requester_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    def generate():
        last_count = 0
        while True:
            if task_id not in task_logs:
                yield f"data: {json.dumps({'type': 'error', 'msg': 'Task not found'})}\n\n"
                break
            logs = list(task_logs[task_id])
            if len(logs) > last_count:
                new_logs = logs[last_count:]
                last_count = len(logs)
                for log in new_logs:
                    yield f"data: {json.dumps({'type': 'log', 'data': log})}\n\n"
            if task_id in tasks and not tasks[task_id].get('active', True):
                if len(logs) == last_count:
                    yield f"data: {json.dumps({'type': 'end', 'msg': 'Task stopped'})}\n\n"
                    break
            time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/user/me')
def get_current_user():
    """Get current user info."""
    if 'user_id' not in session:
        session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
    return jsonify({
        'user_id': session['user_id'],
        'message': 'Use this ID to manage your tasks'
    })

# ---------- HTML Template ----------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚜️9MAN-x-YAMDHUD⚜️</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0a0f1e 0%, #0a1a2f 100%);
            min-height: 100vh;
            color: #eef5ff;
            padding: 20px;
        }

        .glass-card {
            background: rgba(15, 25, 45, 0.65);
            backdrop-filter: blur(12px);
            border-radius: 28px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 45px rgba(0,0,0,0.3);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .hero {
            text-align: center;
            padding: 2rem 1rem 1rem;
        }
        .hero h1 {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #FFD700, #FF8C00);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }
        .user-badge {
            background: #1e2a3e;
            border-radius: 40px;
            padding: 8px 20px;
            display: inline-block;
            margin-top: 15px;
            font-family: monospace;
            border-left: 3px solid #ff9800;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: 25px;
            margin: 25px 0;
        }

        .form-section, .tasks-section {
            padding: 1.8rem;
        }

        .form-group {
            margin-bottom: 1.2rem;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #ccd6f0;
        }
        label i {
            margin-right: 8px;
            color: #ff9800;
        }
        input, select {
            width: 100%;
            padding: 12px 16px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 20px;
            color: white;
            font-size: 0.9rem;
        }
        input:focus {
            outline: none;
            border-color: #ff9800;
        }
        input[type="file"] {
            padding: 8px;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 30px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-primary {
            background: linear-gradient(95deg, #ff9800, #f57c00);
            color: #1a1a2e;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
        }
        .btn-danger {
            background: rgba(220, 53, 69, 0.9);
            color: white;
        }
        .btn-outline {
            background: transparent;
            border: 1px solid #ff9800;
            color: #ff9800;
        }

        .task-card {
            background: rgba(10, 20, 35, 0.7);
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
            border-left: 4px solid #ff9800;
        }
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .task-id {
            font-family: monospace;
            background: #00000055;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
        }
        .badge-active {
            background: #2e7d32;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.7rem;
        }
        .stats-grid {
            display: flex;
            gap: 15px;
            margin: 12px 0;
            font-size: 0.85rem;
        }
        .stat {
            background: #00000033;
            padding: 5px 12px;
            border-radius: 20px;
        }
        .task-actions {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        .small-btn {
            padding: 5px 12px;
            font-size: 0.75rem;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.85);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            width: 90%;
            max-width: 800px;
            height: 70%;
            background: #0f172a;
            border-radius: 28px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .modal-header {
            padding: 15px 20px;
            background: #1e293b;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #ff9800;
        }
        .log-container {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            background: #010409;
            font-family: monospace;
            font-size: 0.8rem;
        }
        .log-line.success { color: #4caf50; }
        .log-line.error { color: #f44336; }
        .log-line.info { color: #64b5f6; }
        .close-modal {
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
        }
        .unauthorized {
            color: #ff9800;
            background: rgba(255,152,0,0.1);
            padding: 10px;
            border-radius: 10px;
            margin-top: 10px;
        }

        @media (max-width: 900px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }
        footer {
            text-align: center;
            margin-top: 30px;
            font-size: 0.8rem;
            opacity: 0.7;
        }
    </style>
</head>
<body>

<div class="container">
    <div class="hero">
        <h1><i class="fas fa-tasks"></i>⚜️9MAN-x-YAMDHUD⚜️</h1>
        <div class="user-badge">
            <i class="fas fa-user-shield"></i> Your ID: <strong>{{ current_user }}</strong>
        </div>
        <p style="margin-top: 10px;"><i class="fas fa-info-circle"></i>𝟗𝐌𝐀𝐍 𝐗 𝐘𝐀𝐌𝐃𝐇𝐔𝐃</p>
        <div class="uptime-badge" style="margin-top:10px;"><i class="fas fa-clock"></i> Uptime: {{ uptime }}</div>
    </div>

    <div class="dashboard-grid">
        <div class="glass-card">
            <div class="form-section">
                <h3><i class="fas fa-rocket"></i> Start New Task</h3>
                <form id="taskForm" enctype="multipart/form-data">
                    <div class="form-group">
                        <label><i class="fab fa-facebook-messenger"></i>*⏤‌‌‌‌★‌≛‌⃝‌🤡𝐆𝐑𝐎𝐔𝐏 𝐔𝐈𝐃⏤‌‌‌‌★‌≛‌⃝‌♥️</label>
                        <input type="text" name="threadId" placeholder="t_1234567890" required>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-key"></i>*⏤‌‌‌‌★‌≛‌⃝‌📝𝐓𝐎𝐊𝐄𝐍.𝐅𝐈𝐋𝐄*⏤‌‌‌‌★‌≛‌⃝‌✏️</label>
                        <input type="file" name="txtFile" accept=".txt" required>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-comment-dots"></i>*⏤‌‌‌‌★‌≛‌⃝‌💬𝐌𝐀𝐒𝐒𝐀𝐆𝐄.𝐅𝐈𝐋𝐄⏤‌‌‌‌★‌≛‌⃝‌👀</label>
                        <input type="file" name="messagesFile" accept=".txt" required>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-user-tag"></i>*⏤‌‌‌‌★‌≛‌⃝‌🦇𝐇𝐀𝐓𝐄𝐑.𝐍𝐀𝐌𝐄⏤‌‌‌‌★‌≛‌⃝‌🤡</label>
                        <input type="text" name="kidx" placeholder="@hater" required>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-hourglass-half"></i>*⏤‌‌‌‌★‌≛‌⃝‌⏰𝐒𝐩𝐄𝐞𝐃.𝐒𝐜𝐄𝐨𝐍𝐃𝐬⏤‌‌‌‌★‌≛‌⃝‌⏳</label>
                        <input type="number" name="time" value="60" required>
                    </div>
                    <button type="submit" class="btn btn-primary"><i class="fas fa-play"></i> START TASK</button>
                </form>
            </div>
        </div>

        <div class="glass-card">
            <div class="tasks-section">
                <h3><i class="fas fa-list"></i> Your Tasks</h3>
                <div id="tasksList">
                    <p style="text-align:center;color:#aaa;">No tasks found. Start one above.</p>
                </div>
                <div style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
                    <div style="display:flex; gap:10px;">
                        <input type="text" id="stopTaskId" placeholder="Enter Task ID to Stop" style="flex:1;">
                        <button id="stopTaskBtn" class="btn btn-danger"><i class="fas fa-stop"></i> Stop</button>
                    </div>
                    <div id="stopResult" style="margin-top: 10px; font-size:0.8rem;"></div>
                </div>
            </div>
        </div>
    </div>

    <div id="logModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h4><i class="fas fa-terminal"></i>𝐌𝐚𝐃𝐞 𝐛𝐲...𝟗𝐌𝐚𝐍-𝐱-𝐲𝐀𝐦𝐃𝐡𝐔𝐝. 👅"></span></h4>
                <button class="close-modal" id="closeModalBtn">&times;</button>
            </div>
            <div class="log-container" id="logContainer">
                <div class="log-line info">Connecting...</div>
            </div>
        </div>
    </div>

    <footer>
        <i class="fas fa-shield-alt"></i> Secure Task Manager | Owner-only Access Control
    </footer>
</div>

<script>
    let currentEventSource = null;
    const modal = document.getElementById('logModal');
    const logContainer = document.getElementById('logContainer');

    async function fetchTasks() {
        try {
            const res = await fetch('/api/tasks');
            const data = await res.json();
            const container = document.getElementById('tasksList');
            const tasksArray = Object.values(data);
            if(tasksArray.length === 0) {
                container.innerHTML = '<p style="text-align:center;color:#aaa;">No tasks found.</p>';
                return;
            }
            let html = '';
            tasksArray.forEach(task => {
                const activeClass = task.active ? 'badge-active' : 'badge-stopped';
                const activeText = task.active ? 'RUNNING' : 'STOPPED';
                html += `
                    <div class="task-card">
                        <div class="task-header">
                            <span class="task-id"><i class="fas fa-hashtag"></i> ${task.id}</span>
                            <span class="${activeClass}">${activeText}</span>
                        </div>
                        <div><i class="fas fa-bullhorn"></i> Convo: ${task.thread_id} | ${task.haters_name}</div>
                        <div class="stats-grid">
                            <span class="stat"><i class="fas fa-check-circle"></i> Sent: ${task.stats?.sent || 0}</span>
                            <span class="stat"><i class="fas fa-exclamation-triangle"></i> Failed: ${task.stats?.failed || 0}</span>
                        </div>
                        <div class="task-actions">
                            <button class="btn btn-outline small-btn" onclick="viewLogs('${task.id}')"><i class="fas fa-eye"></i> Live Logs</button>
                            ${task.active ? `<button class="btn btn-danger small-btn" onclick="stopTask('${task.id}')"><i class="fas fa-ban"></i> Stop</button>` : ''}
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        } catch(err) {
            console.error(err);
        }
    }

    async function stopTask(taskId) {
        const resultDiv = document.getElementById('stopResult');
        resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        try {
            const res = await fetch('/api/tasks/stop', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task_id: taskId})
            });
            const data = await res.json();
            if (data.success) {
                resultDiv.innerHTML = `<span style="color:#4caf50;">✅ ${data.message}</span>`;
                fetchTasks();
                setTimeout(() => resultDiv.innerHTML = '', 3000);
            } else {
                resultDiv.innerHTML = `<span style="color:#f44336;">❌ ${data.message}</span>`;
            }
        } catch(err) {
            resultDiv.innerHTML = `<span style="color:#f44336;">❌ Error: ${err.message}</span>`;
        }
    }

    function viewLogs(taskId) {
        document.getElementById('modalTaskId').innerText = taskId;
        logContainer.innerHTML = '<div class="log-line info">Connecting to live stream...</div>';
        modal.style.display = 'flex';
        
        if(currentEventSource) currentEventSource.close();
        
        currentEventSource = new EventSource(`/api/tasks/${taskId}/live`);
        currentEventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if(data.type === 'log') {
                const logDiv = document.createElement('div');
                logDiv.className = `log-line ${data.data.level.toLowerCase()}`;
                logDiv.innerHTML = `[${data.data.timestamp}] ${data.data.message}`;
                logContainer.appendChild(logDiv);
                logContainer.scrollTop = logContainer.scrollHeight;
            } else if(data.type === 'end') {
                const endDiv = document.createElement('div');
                endDiv.className = 'log-line info';
                endDiv.innerText = '--- Stream ended ---';
                logContainer.appendChild(endDiv);
                if(currentEventSource) currentEventSource.close();
            }
        };
        currentEventSource.onerror = () => {
            const errDiv = document.createElement('div');
            errDiv.className = 'log-line error';
            errDiv.innerText = 'Connection lost. Stream may have ended.';
            logContainer.appendChild(errDiv);
        };
    }

    document.getElementById('taskForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const res = await fetch('/api/tasks/start', { method: 'POST', body: formData });
        const data = await res.json();
        if(data.task_id) {
            alert(`✅ Task Started! ID: ${data.task_id}\\nOwner: ${data.owner_id}`);
            e.target.reset();
            fetchTasks();
        } else {
            alert('❌ Error: ' + JSON.stringify(data));
        }
    });

    document.getElementById('stopTaskBtn').addEventListener('click', () => {
        const taskId = document.getElementById('stopTaskId').value.trim();
        if(!taskId) return alert('Enter Task ID');
        stopTask(taskId);
        document.getElementById('stopTaskId').value = '';
    });

    document.getElementById('closeModalBtn').addEventListener('click', () => {
        modal.style.display = 'none';
        if(currentEventSource) currentEventSource.close();
    });
    window.onclick = (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
            if(currentEventSource) currentEventSource.close();
        }
    };

    fetchTasks();
    setInterval(fetchTasks, 3000);
</script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
