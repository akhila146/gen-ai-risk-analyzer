import React, { useState } from 'react';
import axios from 'axios';
import { MessageSquare, X, Send } from 'lucide-react';

export default function ChatBot({ applicationId }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: 'assistant', text: 'Hello! I can answer questions or summarize the uploaded document. How can I help?' }
  ]);
  const [inputMsg, setInputMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMsg.trim() || !applicationId) return;

    const userQuestion = inputMsg.trim();
    setMessages((prev) => [...prev, { sender: 'user', text: userQuestion }]);
    setInputMsg('');
    setLoading(true);

    try {
      const res = await axios.post('http://localhost:8000/api/chat', {
        application_id: applicationId,
        message: userQuestion
      });
      setMessages((prev) => [...prev, { sender: 'assistant', text: res.data.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: 'assistant', text: 'Error contacting assistant. Please ensure the document is uploaded & backend is running.' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button className="floating-chat-trigger" onClick={() => setIsOpen(!isOpen)}>
        <MessageSquare size={22} />
      </button>

      {isOpen && (
        <div className="chat-modal">
          <div className="chat-header">
            <span>AI Assistant ({applicationId || 'No App Selected'})</span>
            <button className="chat-close-btn" onClick={() => setIsOpen(false)}>
              <X size={18} />
            </button>
          </div>

          <div className="chat-messages">
            {messages.map((m, idx) => (
              <div key={idx} className={`chat-msg ${m.sender}`}>
                {m.text}
              </div>
            ))}
            {loading && <div className="chat-msg assistant">Thinking...</div>}
          </div>

          <form className="chat-input-form" onSubmit={sendMessage}>
            <input
              type="text"
              placeholder={applicationId ? "Ask a question..." : "Upload document first"}
              value={inputMsg}
              disabled={!applicationId}
              onChange={(e) => setInputMsg(e.target.value)}
            />
            <button type="submit" disabled={!applicationId || loading}>
              <Send size={14} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}