import sys
import sqlite3
import threading
import base64
from flask import Flask, render_template, jsonify, request, redirect, url_for
from server import MQTT5Server

app = Flask(__name__)

# Global variables
db_name = "mqtt_server.db"
server_instance = MQTT5Server()
server_thread = None
server_running = False


def _get_connection():
    return sqlite3.connect(db_name)


def _decode_payload(payload):
    """Helper function to decode bytes payload to string"""
    if isinstance(payload, bytes):
        try:
            return payload.decode('utf-8')
        except UnicodeDecodeError:
            # If UTF-8 decoding fails, use base64 encoding as fallback
            return base64.b64encode(payload).decode('ascii')
    return payload


# Server control functions
def start_server():
    global server_thread, server_running
    if not server_running:
        print("Starting Server...")
        server_instance.shutdown_event.clear()
        server_thread = threading.Thread(target=server_instance.server_start)
        server_thread.daemon = True
        server_thread.start()
        server_running = True
        print("Server Started")
        return True
    return False


def stop_server():
    global server_thread, server_running
    if server_running:
        print('Stopping server...')
        server_instance.shutdown_event.set()
        server_running = False
        return True
    return False


# Routes
@app.route('/')
def index():
    return render_template('index.html', server_status=server_running)


@app.route('/server/status', methods=['GET'])
def server_status():
    return jsonify({"running": server_running})


@app.route('/server/start', methods=['POST'])
def server_start_route():
    success = start_server()
    return jsonify({"success": success, "running": server_running})


@app.route('/server/stop', methods=['POST'])
def server_stop_route():
    success = stop_server()
    return jsonify({"success": success, "running": server_running})


# API endpoints for data
@app.route('/api/topics', methods=['GET'])
def get_topics():
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT full_path FROM topics ORDER BY full_path")
        topics = [topic[0] for topic in cursor.fetchall()]
        return jsonify(topics)


@app.route('/api/messages/<topic>', methods=['GET'])
def get_messages(topic):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payload, published_at FROM messages
            JOIN topics ON messages.topic_id = topics.id
            WHERE topics.full_path = ?
            ORDER BY published_at DESC
            LIMIT 10
        """, (topic,))
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "payload": _decode_payload(row[0]),
                "published_at": row[1]
            })
        return jsonify(messages)


@app.route('/api/clients', methods=['GET'])
def get_clients():
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT client_id FROM clients
            WHERE connected = 1
            ORDER BY client_id
        """)
        clients = []
        for (client_id,) in cursor.fetchall():
            # Get wildcard subscriptions for this client
            cursor.execute("""
                SELECT topic_filter, qos FROM subscriptions
                WHERE client_id = ? AND topic_filter IS NOT NULL
            """, (client_id,))
            wildcard_subs = [(topic, qos) for topic, qos in cursor.fetchall()]

            # Get direct subscriptions
            cursor.execute("""
                SELECT topics.full_path, subscriptions.qos
                FROM subscriptions
                JOIN topics ON subscriptions.topic_id = topics.id
                WHERE subscriptions.client_id = ? AND subscriptions.topic_id IS NOT NULL
            """, (client_id,))
            direct_subs = [(topic, qos) for topic, qos in cursor.fetchall()]

            # Combine subscriptions
            all_subs = wildcard_subs + direct_subs

            clients.append({
                "client_id": client_id,
                "subscriptions": [{"topic": topic, "qos": qos} for topic, qos in all_subs]
            })
        return jsonify(clients)


@app.route('/api/topics/subscribers', methods=['GET'])
def get_topic_subscribers():
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_path FROM topics ORDER BY full_path")
        topics = []
        for topic_id, full_path in cursor.fetchall():
            cursor.execute("""
                SELECT clients.client_id
                FROM subscriptions
                JOIN clients ON subscriptions.client_id = clients.client_id
                WHERE subscriptions.topic_id = ?
            """, (topic_id,))
            subscribers = [client[0] for client in cursor.fetchall()]
            topics.append({
                "topic": full_path,
                "subscribers": subscribers
            })
        return jsonify(topics)


@app.route('/api/qos_messages', methods=['GET'])
def get_qos_messages():
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT messages.payload, topics.full_path, messages.qos, messages.published_at
            FROM messages
            JOIN topics ON messages.topic_id = topics.id
            WHERE messages.qos IN (1, 2)
            ORDER BY messages.published_at DESC
        """)
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "payload": _decode_payload(row[0]),
                "topic": row[1],
                "qos": row[2],
                "published_at": row[3]
            })
        return jsonify(messages)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8082, debug=True, use_reloader=False)
