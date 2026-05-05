// MonthlyCalendar.jsx
import React, { useState } from 'react'
import Calendar from 'react-calendar'
import 'react-calendar/dist/Calendar.css'

function MonthlyCalendar() {
  const [date, setDate] = useState(new Date())

  return (
    <div>
      <h2 className="panel-heading">Monthly Calendar</h2>
      <Calendar onChange={setDate} value={date} />
    </div>
  )
}

export default MonthlyCalendar
