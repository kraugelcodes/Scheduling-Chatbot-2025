# This project was created from January 2025 to December 2025 as part of the AI Makerspace Nexus at Georgia Tech. It is intended to be run on a linux based system.

# Operation Steps:

### Step 1) Run "git clone https://github.gatech.edu/OLIVES-VIP-VP4-AIMN/M-VA-Sched" to create a local instance of the repository
### Step 2) Run "cd M-VA-Sched" to move into the cloned Repository
### Step 2B) Edit model_path in qwen.py to a valid location of a local transformers LLM model
### Step 3) Run command "sh install.sh" to run the setup file and install all dependencies
### Step 4) Run command "sh run.sh" to start the frontend and backend and launch the app

# File Descriptions:
## Backend:
**Main Files:**

**Backend/App.py:** Defines a Flask-based backend that manages and edits a blank calendar file (working.ics). It communicates with the Qwen model to process user chat messages and automatically generate or modify calendar events, saving each change as a new version in a history queue with undo and redo support. The app also allows users to upload, download, or clear their .ics files while maintaining only valid calendar formatting.  
Flask Endpoints:  
- api/chat (POST): Takes a user message, calls qwen.chat() → qwen.call_sched() to generate an ICS VEVENT, appends it to working.ics, cleans file, saves a history snapshot.
- api/upload (POST): Uploads an .ics file to replace working.ics, cleans it, saves history.
- api/download (GET): Downloads the current working.ics.
- api/clear (POST): Resets working.ics to a minimal blank VCALENDAR, saves history.
- api/undo (POST): Restores the previous version from ics_history.
- api/redo (POST): Restores the next version from ics_history.



**Backend/Scheduler.py:** Scheduling logic for finding candidate time slots in an ICS calendar.
Uses ics_parser.py for ics input into the main "find_optimal_slot" function which
uses a CSP-like approach to find up to three ranked candidate VEVENT blocks
that can be written into the ICS file. The implementation is intentionally
small and heuristic-based (not a full constraint solver) so it's easy to
extend later.  
Key helpers:
 - _merge_intervals: merge overlapping busy intervals
 - _find_gaps: compute free gaps inside a search window
 - _score_slot: small heuristic for ranking slots

Agent Use:
 - find_optimal_slot: public API (accepts an event_request dict)


**Backend/ics_parser.py:** Handles parsing and interpreting calendar data from .ics files. It reads event blocks (VEVENT) and converts them into structured Python dictionaries containing each event’s UID, summary, start and end datetimes, and raw text. Helper functions parse different datetime formats used in ICS files, including all-day and timezone-neutral events. It can then convert parsed events into busy time intervals for scheduling logic and generate human-readable summaries of event times.


**Backend/Qwen.py:** Connects to model path and scheduler.py. Initializes model and scheduling algorithm and interprets NLP into structured data that can be appended to calendar.  



## Frontend:
Main Files:  
**Frontend/index.html:** Contains the actual webpage being launched, which then calls src/App.jsx to display
**Frontend/src/App.css:** Contains frontend styling, buttons, and features.  
**Frontend/src/App.jsx:** Connects frontend to backend and has all methods to handle user actions.
