# app.py (fully updated)
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import re
import datetime
import shutil
import qwen
from collections import deque

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Allow requests from frontend

ICS_FILE_PATH = "working.ics"
ICS_HISTORY_DIR = "ics_history"
os.makedirs(ICS_HISTORY_DIR, exist_ok=True)
MAX_HISTORY = 20
ics_history = deque()
current_index = -1
qwen.launch()

# Ensure a default blank ICS file exists
def initialize_ics_file():
    if not os.path.exists(ICS_FILE_PATH):
        with open(ICS_FILE_PATH, "w") as f:
            f.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Default Calendar//EN\nEND:VCALENDAR\n")

def clean_ics_file():
    try:
        with open(ICS_FILE_PATH, "r") as f:
            content = f.read()
        match = re.search(r"BEGIN:VCALENDAR.*?END:VCALENDAR", content, re.DOTALL)
        if match:
            cleaned_content = match.group(0)
            with open(ICS_FILE_PATH, "w") as f:
                f.write(cleaned_content)
    except Exception as e:
        print(f"Error cleaning ICS file: {e}")

def save_to_history():
    global current_index
    global ics_history
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    history_file = os.path.join(ICS_HISTORY_DIR, f"calendar_{timestamp}.ics")
    #print(history_file)
    shutil.copy2(ICS_FILE_PATH, history_file)
    ics_history.append(history_file)
    print(ics_history)
    if len(ics_history) > MAX_HISTORY:
        os.remove(ics_history.popleft())
    current_index = len(ics_history) - 1

def restore_file(index):
    if 0 <= index < len(ics_history):
        shutil.copy2(ics_history[index], ICS_FILE_PATH)
        clean_ics_file()
        return True
    return False

initialize_ics_file()


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400

        with open(ICS_FILE_PATH, "r") as f:
            file_content = f.read()

        response = qwen.chat(user_message, file_content)
        print(response)

        if response != None:
            try:
                event_dict = qwen.call_sched(response)
                #print(event_dict)

                if type(event_dict) == str:
                    print(event_dict)
                    clean_ics_file()
                    save_to_history()
                    return jsonify({"changes": event_dict, "timestamp": current_datetime}), 200

                events = []

                for rank in sorted(event_dict.keys()):
                    events.append({"rank": rank, "event": event_dict[rank]})

                return jsonify({"options": events, "timestamp": current_datetime}), 200
            except ValueError as e2:
                response = qwen.chat(user_message)
                event_dict = qwen.call_sched(response)
                #print(event_dict)

                events = []

                for rank in sorted(event_dict.keys()):
                    events.append({"rank": rank, "event": event_dict[rank]})

                return jsonify({"options": events, "timestamp": current_datetime}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

'''
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400

        with open(ICS_FILE_PATH, "r") as f:
            file_content = f.read()

        response = qwen.chat(user_message, file_content)
        print(response)

        try:
            event_dict = qwen.call_sched(response)
            #print(event_dict)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

        #Edit/Delete Event

        if type(event_dict) == str:
            return jsonify({"changes": event_dict, "timestamp": current_datetime}), 200

        #Add Event

        events = []

        for rank in sorted(event_dict.keys()):
            events.append({"rank": rank, "event": event_dict[rank]})

        return jsonify({"options": events, "timestamp": current_datetime}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
'''
@app.route('/api/select_event', methods=['POST'])
def select_event():
    try:
        data = request.get_json()
        selected_event = data.get("event")
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not selected_event:
            return jsonify({"error": "No event selected"}), 400

        #read current .ics file
        with open(ICS_FILE_PATH, "r") as f:
            file_content = f.read()

        #append selected_event
        
        updated_file_content = file_content.split("END:VCALENDAR")[0] +     selected_event + "\n" + "END:VCALENDAR"
        #updated_file_content = file_content.rstrip().removesuffix("END:VCALENDAR").rstrip() + "\n" + selected_event + "\nEND:VCALENDAR\n"
        print(updated_file_content)

        #write updated .ics file
        with open(ICS_FILE_PATH, "w") as f:
            f.write(updated_file_content)

        clean_ics_file()
        save_to_history()
        return jsonify({"changes": selected_event, "timestamp": current_datetime}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400

        file_content = file.read().decode('utf-8')
        with open(ICS_FILE_PATH, "w") as f:
            f.write(file_content)
        clean_ics_file()
        save_to_history()
        return jsonify({"message": "ICS file uploaded successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_file():
    try:
        return send_file(ICS_FILE_PATH, as_attachment=True, mimetype='text/calendar', download_name='calendar.ics')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_ics_file():
    try:
        with open(ICS_FILE_PATH, "w") as f:
            f.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Default Calendar//EN\nEND:VCALENDAR\n")
        save_to_history()
        return jsonify({"message": "ICS file cleared successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/undo', methods=['POST'])
def undo():
    global current_index
    if current_index > 0:
        current_index -= 1
        if restore_file(current_index):
            return jsonify({"message": "Undo successful"})
    return jsonify({"error": "Nothing to undo"}), 400

@app.route('/api/redo', methods=['POST'])
def redo():
    global current_index
    if current_index < len(ics_history) - 1:
        current_index += 1
        if restore_file(current_index):
            return jsonify({"message": "Redo successful"})
    return jsonify({"error": "Nothing to redo"}), 400

#GTEngage API Framework (DEMO)
ENGAGE_API_TOKEN = ""
ENGAGE_BASE_URL = "https://engage-api.campuslabs.com/api"
import requests
def configure_engage(api_token):
    global ENGAGE_API_TOKEN 
    ENGAGE_API_TOKEN = api_token

@app.route('/api/configure-engage', methods=['POST'])
def configure_engage_api():
    """Configure Engage API token (optional - can override environment variable)"""
    try:
        data = request.get_json()
        api_token = data.get("apiToken", "")
        if not api_token:
            return jsonify({"error": "Engage API token is required"}), 400
        
        configure_engage(api_token)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_engage_events(categories=None, limit=20):
    """Fetch events from Engage API based on categories"""
    try:
        headers = {
            'Authorization': f'Bearer {ENGAGE_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'limit': limit,
            'startDate': datetime.datetime.now().isoformat(),
            'endDate': (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        }
        
        if categories:
            params['categories'] = ','.join(categories)
        
        response = requests.get(f"{ENGAGE_BASE_URL}/events/event", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Engage events: {e}")
        return None



if __name__ == '__main__':
    app.run(debug=True, port=5000)
