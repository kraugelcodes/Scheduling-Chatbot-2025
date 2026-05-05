
#!/bin/bash
xfce4-terminal --command  "bash -i  -c 'cd ./frontend/; npm install; npm run dev; bash -i'"
#!/bin/bash
echo "Setting up the virtual environment..."

cd ./backend/
source venv/bin/activate

xdg-open "http://localhost:5173"
python3 app.py
