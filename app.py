from flask import Flask, request, render_template_string, jsonify, Response
import requests
import time
import threading
import secrets
import os
from datetime import datetime
import json
import queue

app = Flask(__name__)

# Generate unique ADMIN_KEY on server start
ADMIN_KEY = secrets.token_hex(16)
print(f"\n{'='*50}")
print(f"[!] ⚜️ 9MAN-x-YAMDHUD ⚜️")
print(f"[!] ADMIN_KEY: {ADMIN_KEY}")
print(f"[!] Save this key to stop the attack!")
print(f"{'='*50}\n")

# Global variables
attack_running = False
attack_thread = None
log_queue = queue.Queue()
stats = {
    'total_sent': 0,
    'total_failed': 0,
    'start_time': None,
    'current_speed': 0
}

# Server start time
SERVER_START_TIME = datetime.now()

# Default messages (built-in, no need to upload)
DEFAULT_MESSAGES = [
    "You are a loser!",
    "Get a life!",
    "Stop wasting time!",
    "You got owned!",
    "Hahaha pathetic!",
    "Go cry somewhere else!",
    "You have been hacked!",
    "Better luck next time!",
    "What a joke!",
    "Stay mad!",
    "L + Ratio + You fell off!",
    "Touch some grass!",
    "You are finished!",
    "Take the L!",
    "Cope harder!",
    "Rent free!",
    "Cry about it!",
    "Stay salty!",
    "Get rekt!",
    "EZ clap!"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def attack_worker(thread_id, mn, time_interval, access_tokens):
    global attack_running, stats
    num_comments = len(DEFAULT_MESSAGES)
    max_tokens = len(access_tokens)
    post_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
    haters_name = mn
    speed = time_interval
    message_index = 0
    
    stats['start_time'] = datetime.now()
    
    while attack_running:
        try:
            token_index = message_index % max_tokens
            access_token = access_tokens[token_index].strip()
            message = DEFAULT_MESSAGES[message_index % num_comments]
            
            if not access_token:
                message_index += 1
                continue
            
            parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
            response = requests.post(post_url, json=parameters, headers=headers, timeout=10)
            
            current_time = datetime.now().strftime("%H:%M:%S")
            
            if response.ok:
                stats['total_sent'] += 1
                log_queue.put(f"[+] SENT | {haters_name} {message} | Token {token_index+1} | {current_time}")
            else:
                stats['total_failed'] += 1
                log_queue.put(f"[x] FAILED | Token {token_index+1} | Error {response.status_code} | {current_time}")
            
            message_index += 1
            stats['current_speed'] = speed
            time.sleep(speed)
            
        except Exception as e:
            log_queue.put(f"[!] ERROR: {str(e)[:80]}")
            stats['total_failed'] += 1
            time.sleep(5)

def get_uptime():
    delta = datetime.now() - SERVER_START_TIME
    return f"{delta.days}d {delta.seconds//3600}h {(delta.seconds%3600)//60}m {delta.seconds%60}s"

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚜️ 9MAN-x-YAMDHUD ⚜️</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Orbitron', monospace;
            background: linear-gradient(135deg, #0a0f1e 0%, #000000 100%);
            min-height: 100vh;
            color: #0f0;
        }
        .glow {
            text-shadow: 0 0 10px #0f0, 0 0 20px #0f0;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        /* Header */
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 25px;
            background: rgba(0,0,0,0.7);
            border: 2px solid #0f0;
            border-radius: 20px;
            box-shadow: 0 0 30px rgba(0,255,0,0.2);
        }
        .header h1 {
            font-size: 2.5rem;
            color: #0f0;
            letter-spacing: 5px;
        }
        .header p { color: #0a0; font-size: 0.8rem; margin-top: 10px; }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(0,0,0,0.8);
            border: 1px solid #0f0;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 0 20px rgba(0,255,0,0.3); }
        .stat-card i { font-size: 2rem; color: #0f0; margin-bottom: 10px; }
        .stat-card .value { font-size: 1.8rem; font-weight: bold; color: #0f0; }
        .stat-card .label { font-size: 0.7rem; color: #0a0; margin-top: 5px; }
        
        /* Main Content */
        .main-content { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
        @media (max-width: 900px) { .main-content { grid-template-columns: 1fr; } }
        
        .panel {
            background: rgba(0,0,0,0.8);
            border: 1px solid #0f0;
            border-radius: 20px;
            padding: 25px;
        }
        .panel h2 {
            color: #0f0;
            margin-bottom: 20px;
            font-size: 1.3rem;
            border-bottom: 1px solid #0f0;
            padding-bottom: 10px;
        }
        
        .input-group { margin-bottom: 20px; }
        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #0f0;
            font-size: 0.85rem;
        }
        .input-group input {
            width: 100%;
            padding: 12px;
            background: #111;
            border: 1px solid #0f0;
            border-radius: 10px;
            color: #0f0;
            font-family: monospace;
        }
        .input-group input:focus {
            outline: none;
            box-shadow: 0 0 10px #0f0;
        }
        .file-input input {
            padding: 10px;
            cursor: pointer;
        }
        
        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 10px;
            font-weight: bold;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s;
            font-family: 'Orbitron', monospace;
            margin-bottom: 10px;
        }
        .btn-primary {
            background: #0f0;
            color: #000;
        }
        .btn-primary:hover {
            background: #0a0;
            box-shadow: 0 0 20px #0f0;
        }
        .btn-danger {
            background: #f00;
            color: #fff;
        }
        .btn-danger:hover {
            background: #c00;
            box-shadow: 0 0 20px #f00;
        }
        
        .logs-container {
            background: #000;
            border-radius: 10px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.75rem;
        }
        .log-entry {
            padding: 5px;
            border-left: 3px solid #0f0;
            margin-bottom: 5px;
            color: #0f0;
            word-break: break-word;
        }
        .log-entry.failed { border-left-color: #f00; color: #f66; }
        .log-entry.error { border-left-color: #ff0; color: #ff6; }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #000;
            border: 2px solid #0f0;
            border-radius: 20px;
            padding: 30px;
            width: 90%;
            max-width: 400px;
            text-align: center;
        }
        .modal-content input {
            width: 100%;
            padding: 12px;
            margin: 20px 0;
            background: #111;
            border: 1px solid #0f0;
            color: #0f0;
        }
        
        .badge-running {
            animation: pulse 1s infinite;
            background: #0f0;
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
        }
        .badge-stopped {
            background: #f00;
            color: #fff;
            padding: 4px 12px;
            border-radius: 20px;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #0a0;
            font-size: 0.7rem;
        }
        
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #111; }
        ::-webkit-scrollbar-thumb { background: #0f0; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-skull"></i> ⚜️ 9MAN-x-YAMDHUD ⚜️ <i class="fas fa-bolt"></i></h1>
            <p>FACEBOOK MESSENGER AUTO-SENDER | ENTERPRISE EDITION</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><i class="fas fa-paper-plane"></i><div class="value" id="totalSent">0</div><div class="label">SENT</div></div>
            <div class="stat-card"><i class="fas fa-times-circle"></i><div class="value" id="totalFailed">0</div><div class="label">FAILED</div></div>
            <div class="stat-card"><i class="fas fa-chart-line"></i><div class="value" id="totalMessages">0</div><div class="label">TOTAL</div></div>
            <div class="stat-card"><i class="fas fa-tachometer-alt"></i><div class="value" id="currentSpeed">0</div><div class="label">SPEED (sec)</div></div>
            <div class="stat-card"><i class="fas fa-clock"></i><div class="value" id="uptime">0</div><div class="label">UPTIME</div></div>
            <div class="stat-card"><i class="fas fa-microchip"></i><div id="attackStatus" class="badge-stopped" style="display: inline-block;">STOPPED</div><div class="label">STATUS</div></div>
        </div>

        <div class="main-content">
            <div class="panel">
                <h2><i class="fas fa-cogs"></i> CONTROL PANEL</h2>
                <form id="attackForm" enctype="multipart/form-data">
                    <div class="input-group">
                        <label><i class="fas fa-comment-dots"></i> CONVO ID / THREAD ID</label>
                        <input type="text" name="threadId" placeholder="Enter conversation ID" required>
                    </div>
                    <div class="input-group file-input">
                        <label><i class="fas fa-key"></i> TOKENS FILE (.txt) - ONLY FILE NEEDED</label>
                        <input type="file" name="txtFile" accept=".txt" required>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-user-tag"></i> HATER NAME / PREFIX</label>
                        <input type="text" name="kidx" placeholder="e.g., X_HATER X" required>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-hourglass-half"></i> SPEED DELAY (seconds)</label>
                        <input type="number" name="time" value="5" min="1" required>
                    </div>
                    <button type="submit" class="btn btn-primary" id="startBtn"><i class="fas fa-play"></i> START ATTACK</button>
                </form>
                <button class="btn btn-danger" id="stopBtn"><i class="fas fa-stop"></i> STOP ATTACK</button>
                <div style="margin-top: 15px; text-align: center; font-size: 0.7rem; color: #0a0;">
                    <i class="fas fa-dice-d6"></i> 20+ Built-in Messages | No NP File Required
                </div>
            </div>

            <div class="panel">
                <h2><i class="fas fa-terminal"></i> LIVE CONSOLE</h2>
                <button id="clearLogsBtn" style="margin-bottom: 10px; padding: 5px 10px; background: #111; border: 1px solid #0f0; color: #0f0; cursor: pointer;"><i class="fas fa-trash"></i> CLEAR</button>
                <div class="logs-container" id="logsContainer">
                    <div class="log-entry">[!] System ready. Waiting for commands...</div>
                    <div class="log-entry">[!] Upload tokens file and start attack</div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>⚡ 9MAN-x-YAMDHUD | 364 DAYS UPTIME GUARANTEED | ADMIN KEY REQUIRED TO STOP ⚡</p>
        </div>
    </div>

    <div id="stopModal" class="modal">
        <div class="modal-content">
            <i class="fas fa-lock" style="font-size: 3rem; color: #0f0;"></i>
            <h3>ADMIN AUTHENTICATION</h3>
            <input type="password" id="adminKeyInput" placeholder="Enter ADMIN KEY">
            <div style="display: flex; gap: 10px;">
                <button id="confirmStopBtn" style="flex:1; background: #f00; color: #fff; padding: 10px; border: none; cursor: pointer;">STOP</button>
                <button id="cancelStopBtn" style="flex:1; background: #333; color: #fff; padding: 10px; border: none; cursor: pointer;">CANCEL</button>
            </div>
        </div>
    </div>

    <script>
        const ADMIN_KEY = '{{ admin_key }}';
        
        function addLog(msg, type='success') {
            const container = document.getElementById('logsContainer');
            const div = document.createElement('div');
            div.className = `log-entry ${type === 'failed' ? 'failed' : (type === 'error' ? 'error' : '')}`;
            div.innerHTML = msg;
            container.appendChild(div);
            div.scrollIntoView({ behavior: 'smooth', block: 'end' });
            while(container.children.length > 300) container.removeChild(container.firstChild);
        }
        
        async function fetchStats() {
            try {
                const res = await fetch('/stats');
                const s = await res.json();
                document.getElementById('totalSent').innerText = s.total_sent;
                document.getElementById('totalFailed').innerText = s.total_failed;
                document.getElementById('totalMessages').innerText = s.total_messages;
                document.getElementById('currentSpeed').innerText = s.current_speed;
                document.getElementById('uptime').innerText = s.uptime;
                const statusEl = document.getElementById('attackStatus');
                if (s.attack_active) {
                    statusEl.className = 'badge-running';
                    statusEl.innerText = 'RUNNING';
                } else {
                    statusEl.className = 'badge-stopped';
                    statusEl.innerText = 'STOPPED';
                }
            } catch(e) {}
        }
        
        let eventSource = null;
        function setupSSE() {
            if(eventSource) eventSource.close();
            eventSource = new EventSource('/logs/stream');
            eventSource.onmessage = (e) => {
                const logs = JSON.parse(e.data);
                logs.forEach(log => {
                    let type = 'success';
                    if(log.includes('FAILED')) type = 'failed';
                    else if(log.includes('ERROR')) type = 'error';
                    addLog(log, type);
                });
            };
            eventSource.onerror = () => setTimeout(setupSSE, 3000);
        }
        
        document.getElementById('attackForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            document.getElementById('startBtn').disabled = true;
            document.getElementById('startBtn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> STARTING...';
            try {
                const res = await fetch('/start', { method: 'POST', body: formData });
                const data = await res.json();
                addLog(data.status === 'success' ? '[+] Attack started!' : '[x] ' + data.message, data.status === 'success' ? 'success' : 'failed');
            } catch(e) { addLog('[x] Error: ' + e.message, 'failed'); }
            document.getElementById('startBtn').disabled = false;
            document.getElementById('startBtn').innerHTML = '<i class="fas fa-play"></i> START ATTACK';
        };
        
        document.getElementById('stopBtn').onclick = () => document.getElementById('stopModal').style.display = 'flex';
        document.getElementById('confirmStopBtn').onclick = async () => {
            const key = document.getElementById('adminKeyInput').value;
            document.getElementById('stopModal').style.display = 'none';
            document.getElementById('adminKeyInput').value = '';
            try {
                const res = await fetch('/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ admin_key: key }) });
                const data = await res.json();
                addLog(data.status === 'success' ? '[+] Attack stopped!' : '[x] ' + data.message, data.status === 'success' ? 'success' : 'failed');
            } catch(e) { addLog('[x] Error: ' + e.message, 'failed'); }
        };
        document.getElementById('cancelStopBtn').onclick = () => { document.getElementById('stopModal').style.display = 'none'; document.getElementById('adminKeyInput').value = ''; };
        document.getElementById('clearLogsBtn').onclick = () => { document.getElementById('logsContainer').innerHTML = ''; addLog('[!] Logs cleared', 'error'); };
        
        setupSSE();
        fetchStats();
        setInterval(fetchStats, 2000);
        addLog('[!] Ready | Uptime 364 days guaranteed', 'error');
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, admin_key=ADMIN_KEY)

@app.route('/start', methods=['POST'])
def start_attack():
    global attack_running, attack_thread, stats
    
    if attack_running:
        return jsonify({'status': 'error', 'message': 'Attack already running!'})
    
    thread_id = request.form.get('threadId')
    mn = request.form.get('kidx')
    time_interval = int(request.form.get('time'))
    
    txt_file = request.files['txtFile']
    access_tokens = txt_file.read().decode().splitlines()
    access_tokens = [t.strip() for t in access_tokens if t.strip()]
    
    if not access_tokens:
        return jsonify({'status': 'error', 'message': 'Tokens file is empty!'})
    
    stats = {'total_sent': 0, 'total_failed': 0, 'start_time': None, 'current_speed': time_interval}
    
    attack_running = True
    attack_thread = threading.Thread(target=attack_worker, args=(thread_id, mn, time_interval, access_tokens), daemon=True)
    attack_thread.start()
    
    return jsonify({'status': 'success', 'message': 'Attack started!'})

@app.route('/stop', methods=['POST'])
def stop_attack():
    global attack_running
    data = request.get_json()
    if data.get('admin_key') == ADMIN_KEY:
        attack_running = False
        return jsonify({'status': 'success', 'message': 'Attack stopped!'})
    return jsonify({'status': 'error', 'message': 'Invalid Admin Key!'})

@app.route('/stats')
def get_stats():
    total = stats['total_sent'] + stats['total_failed']
    return jsonify({
        'total_sent': stats['total_sent'],
        'total_failed': stats['total_failed'],
        'total_messages': total,
        'current_speed': stats['current_speed'],
        'attack_active': attack_running,
        'uptime': get_uptime()
    })

@app.route('/logs/stream')
def stream_logs():
    def generate():
        sent = set()
        while True:
            while not log_queue.empty():
                log = log_queue.get_nowait()
                if log not in sent:
                    sent.add(log)
                    yield f"data: {json.dumps([log])}\n\n"
            time.sleep(0.5)
    return Response(generate(), mimetype="text/event-stream")

if __name__ == '__main__':
    print("\n[!] Server Starting...")
    print("[!] Open browser and go to: http://localhost:5000")
    print("[!] Press CTRL+C to stop server\n")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
