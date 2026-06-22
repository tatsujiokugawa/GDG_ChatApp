import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meet_backchat_secret_key'

# 自動で最適な非同期モード（eventletなど）を選択
socketio = SocketIO(app, cors_allowed_origins="*")

# -------------------------------------------------------------------------
# Completely English & Accessibility-friendly HTML Template
# -------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GDG Discussion Chat</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 20px auto; padding: 0 10px; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
        #chat-log { border: 2px solid #ccc; height: 400px; overflow-y: scroll; padding: 15px; margin-bottom: 15px; background: #f9f9f9; }
        .message { margin-bottom: 10px; padding: 8px; border-bottom: 1px solid #eee; }
        .input-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input[type="text"] { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
    </style>
</head>
<body>

    <header>
        <h1>GDG Discussion Chat</h1>
        <p>A real-time chatroom for all Global Discussion Group members:</p>
    </header>

    <main>
        <section aria-labelledby="log-heading">
            <h2 id="log-heading" class="sr-only">Chat History</h2>
            <div id="chat-log" role="log" aria-live="polite" aria-relevant="additions">
                <div class="message"><em>System: Connected to the chatroom. Waiting for messages...</em></div>
            </div>
        </section>

        <section aria-labelledby="form-heading">
            <h2 id="form-heading" class="sr-only">Send a Message</h2>
            
            <div class="input-group">
                <label for="username">Your Name</label>
                <input id="username" type="text" placeholder="e.g., John" autocomplete="name">
            </div>

            <div class="input-group">
                <label for="myMessage">Message</label>
                <input id="myMessage" type="text" placeholder="Type your message here and press Enter" onkeypress="handleKeyPress(event)">
            </div>

            <button onclick="sendMessage()">Send</button>
        </section>
    </main>

    <script>
        var socket = io();

        // When a new message is received from the server
        socket.on('message', function(data) {
            var log = document.getElementById('chat-log');
            var div = document.createElement('div');
            div.className = 'message';
            
            // Format so that screen readers read it naturally as "Name: Message"
            div.innerHTML = '<strong>' + data.user + ':</strong> ' + data.msg;
            log.appendChild(div);
            
            // Auto-scroll to the bottom
            log.scrollTop = log.scrollHeight;
        });

        // Function to send a message
        function sendMessage() {
            var userField = document.getElementById('username');
            var msgField = document.getElementById('myMessage');
            
            var user = userField.value.trim() || 'Anonymous';
            var msg = msgField.value.trim();
            
            if(msg) {
                socket.emit('message', {user: user, msg: msg});
                msgField.value = '';
                msgField.focus(); // Keep focus on the input for continuous typing
            }
        }

        // Allow sending message with Enter key
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('message')
def handle_message(data):
    emit('message', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)