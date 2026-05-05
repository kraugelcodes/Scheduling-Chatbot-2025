// GroupSchedule.jsx
import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import ChatPanel from './components/ChatPanel';
import DailyTasks from './components/DailyTasks';
import { Calendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { parseICS } from './utils/icsParser';
import IndividualSchedule from "./App";

const localizer = momentLocalizer(moment);

function GroupSchedule() {
  const [chatResponse, setChatResponse] = useState([]);
  const [fileContent, setFileContent] = useState('');
  const [events, setEvents] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [calendarView, setCalendarView] = useState('month');
  const [calendarDate, setCalendarDate] = useState(new Date());
  const [apiKey, setApiKey] = useState('');
  const [message, setMessage] = useState('');
  const [showIndividualSchedule, setShowIndividualSchedule] = useState(false);

  useEffect(() => {
    fetchICSFile();
  }, []);

  useEffect(() => {
    if (chatResponse) {
      fetchICSFile();
    }
  }, [chatResponse]);

  useEffect(() => {
    document.body.className = darkMode ? 'dark-mode' : 'light-mode';
  }, [darkMode]);

  useEffect(() => {
    if (Array.isArray(events) && events.length > 0) {
      setTimeout(() => {
        window.dispatchEvent(new Event("resize"));
      }, 100);
    }
  }, [JSON.stringify(events)]);

  const fetchICSFile = () => {
    fetch('http://localhost:5000/api/download')
      .then((res) => res.text())
      .then((icsData) => {
        const parsedEvents = parseICS(icsData);
        setEvents(parsedEvents);
      })
      .catch((err) => console.error("Failed to fetch ICS file:", err));
  };

  const handleChatSend = (message) => {
    fetch('http://localhost:5000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    })
      .then((res) => res.json())
      .then((data) => {
        setChatResponse(data.options);
        //setChatResponse(data.changes);
        //fetchICSFile();
        setMessage('');
      })
      .catch((err) => console.error(err));
  };

  const handleSelectEvent = (eventSelected) => {
    fetch('http://localhost:5000/api/select_event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event: eventSelected })
    })
      .then((res) => res.json())
      .then((data) => {
        fetchICSFile();
      })
      .catch((err) => console.error(err));
  }

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    fetch('http://localhost:5000/api/upload', {
      method: 'POST',
      body: formData,
    })
      .then((res) => res.json())
      .then(() => {
        setFileContent("ICS file uploaded successfully.");
        fetchICSFile();
      })
      .catch((err) => console.error(err));
  };

  const handleClearICS = () => {
    fetch('http://localhost:5000/api/clear', {
      method: 'POST',
    })
      .then((res) => res.json())
      .then(() => {
        setFileContent("ICS file cleared.");
        setEvents([]);
      })
      .catch((err) => console.error("Failed to clear ICS file:", err));
  };

  const handleDownloadICS = () => {
    fetch('http://localhost:5000/api/download')
      .then((response) => response.blob())
      .then((blob) => {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'calendar.ics';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      })
      .catch((err) => console.error(err));
  };

  const handleUndo = () => {
    fetch('http://localhost:5000/api/undo', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (data.message) {
          fetchICSFile();
          alert("Undo successful");
        } else {
          alert(data.error);
        }
      });
  };

  const handleRedo = () => {
    fetch('http://localhost:5000/api/redo', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (data.message) {
          fetchICSFile();
          alert("Redo successful");
        } else {
          alert(data.error);
        }
      });
  };

  const handleAPIKeySubmit = () => {
    fetch('http://localhost:5000/api/set-api-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apiKey })
    })
      .then((res) => res.json())
      .then((data) => alert(data.message))
      .catch((err) => console.error(err));
  };

  //GT Engage API Framework (DEMO)
  /** Returns a paged list of events as a JSON
   *  This call uses parametrs to search for events within a specific category with ID 12345
   *  It also limits events to certain dates and times
   *  Sets a list length limit of 50
  **/
  const getEvents = () => {
    fetch('https://engage-api.campuslabs.com/api/v3.0/events/event', {
      method: 'GET',
      headers: {
        'Authorization': 'API_KEY_HERE',
        'Content-Type': 'application/json'
      },
      params: {
        'categoryId': 12345,
        'startDate': '2025-01-01T00:00:00Z',
        'endDate': '2025-12-31T23:59:59Z',
        'limit': 50
      }

    })
    .then(response => response.json())
    .then(events => console.log(events));
  }
  /** Creates an RSVP to event with ID {eventId}
   *  Need to get the userId somehow
   *  Can also set rsvp status to not_attending, or maybe
  **/
    const makeRSVP = () => {
    fetch('https://engage-api.campuslabs.com/api/v3.0/events/event/{eventId}/rsvp', {
      method: 'POST',
      headers: {
        'Authorization': 'API_KEY_HERE',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        "userId": "user123",
        "status": "attending"
      })
    })
    .then(response => response.json())
    .then(rsvp => console.log(rsvp));
  }




  const handleEventSelect = (event) => {
    alert(`Event: ${event.title}\nStart: ${event.start}\nEnd: ${event.end}`);
  };

  const fileInputRef = useRef(null);
  const handlePlusClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }

  const handleKeyDown = (e) => {
    if (e.key == "Enter") {
      handleChatSend(message);
    }
  }

  if (showIndividualSchedule) {
    return <IndividualSchedule />;
  }

  return (
    <>
      {/* Top Panel */}
      <div className="top-panel">

        {/* Logo Section */}
        <div className="logo-design">
          <div>
            <img 
              src="/images/buzz-logo.png"
              height="55" 
              alt="Buzz" 
              style={{float: "left"}}
            />
          </div>
          <div>
            <label htmlFor="logo">BuzzSync</label>
          </div>
        </div>

        {/* Individual Scheduler */}

        <div className="logo-design">
          <div>
            <img 
              src="/images/one-person.webp"
              height="55" 
              alt="Individual Scheduler" 
              style={{float: "left"}}
              onClick={() => setShowIndividualSchedule(true)}
            />
          </div>
          <div>
            <label htmlFor="individual-scheduler">Your Schedule</label>
          </div>
        </div>

        {/* Group Scheduler */}

        <div className="logo-design">
          <div>
            <img 
              src="/images/group-people.png"
              height="55" 
              alt="Group Scheduler" 
              style={{float: "left"}}
            />
          </div>
          <div>
            <label htmlFor="group-scheduler">Team Schedule</label>
          </div>
        </div>

      </div>

      <div className="main-container">

        {/* Left Panel */}
        <div className="left-panel">

          {/* Search bar & file upload */}
          <div className="prompt">
            <div className="search-bar">
		<input type="text" placeholder="Ask Buzz..." value={message} onChange = {(e) => setMessage(e.target.value)} onKeyDown={handleKeyDown}/>
            </div>
            <div className="file-upload">
              <input type="file" accept=".txt" style={{display: "none",}} ref={fileInputRef} onChange={handleFileUpload}/>
              <button type="button" className = "plus-button" onClick={handlePlusClick}>+</button>
              <pre className="file-content">{fileContent}</pre>
            </div>
          </div>

          {/* Gemini response */}
          <div className="chat-response">

          {/* Chat response (3 options presented to user) */}
          {chatResponse && chatResponse.length > 0 ? (
            chatResponse.map((opt) => (
              <div key={opt.rank} className="event-option">
                <pre>{opt.event}</pre>
                <button onClick={() => handleSelectEvent(opt.event)}>Choose this</button>
              </div>
            ))
          ) : (
            <p>Suggestions will appear here.</p>
          )}

          </div>

          <div className="controls" style={{display: "flex", gap: "10px", marginTop: "15px"}}>
            <button className="button" onClick={handleClearICS}>Clear Calendar</button>
            <button className="button" onClick={handleUndo}>Undo</button>
            <button className="button" onClick={handleRedo}>Redo</button>
            <button className="button" onClick={handleDownloadICS}>Download as .ics</button>
          </div>
        </div>

        {/* Calendar Panel */}
        <div className="middle-panel" style={{width: '75%'}}>
          <p>Team Schedule</p>
          <Calendar
            localizer={localizer}
            events={events}
            startAccessor="start"
            endAccessor="end"
            style={{ height: 700 }}
            view={calendarView}
            date={calendarDate}
            onNavigate={(date) => setCalendarDate(date)}
            onView={(view) => setCalendarView(view)}
            onSelectEvent={handleEventSelect}
          />
        </div>
      </div>
    </>
  );
}
export default GroupSchedule;

