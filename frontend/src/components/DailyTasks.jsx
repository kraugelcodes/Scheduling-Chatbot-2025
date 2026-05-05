// DailyTasks.jsx
import React, { useState, useEffect } from 'react'

function DailyTasks() {
  const [tasks, setTasks] = useState([])

  useEffect(() => {
    fetch('/api/calendar/events/today')
      .then((res) => res.json())
      .then((data) => setTasks(data.events))
      .catch((err) => console.error(err))
  }, [])

  return (
    <div>
      <h2 className="panel-heading">Today's Tasks</h2>
      <ul className="tasks-list">
        {tasks.map((task) => (
          <li key={task.id}>
            <strong>{task.summary}</strong>
            <div>
              {task.start.dateTime || task.start.date}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default DailyTasks
