// ChatPanel.jsx
import React, { useState } from 'react'

function ChatPanel({ onSend }) {
  const [message, setMessage] = useState('')

  const handleSend = () => {
    if (message.trim()) {
      onSend(message)
      setMessage('')
    }
  }

  return (
    <div>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={5}
        className="chat-textarea"  // add a class name
        placeholder="Enter your command here..."
      />
      <button className="chat-button" onClick={handleSend}>Send</button>
    </div>
  )
}

export default ChatPanel
