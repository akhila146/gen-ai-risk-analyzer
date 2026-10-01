import React, { useState } from 'react';
import axios from 'axios';
import { MessageSquare, X, Send } from 'lucide-react';

const APP_ID_PATTERN = /\b[A-Z]+-\d+(?:-[A-Z0-9]+)*\b/g;

function renderMessageWithBadges(text, onSelectApplication) {
  const matches = [...text.matchAll(APP_ID_PATTERN)];

  if (!matches.length) {
    return text;
  }

  const parts = [];
  let cursor = 0;

  matches.forEach((match, index) => {
    const appId = match[0];
    const startIndex = match.index ?? 0;

    if (startIndex > cursor) {
      parts.push(text.slice(cursor, startIndex));
    }

    parts.push(
      <button
        key={`${appId}-${index}`}
        type="button"
        className="chat-app-badge"
        onClick={() => onSelectApplication?.(appId)}
      >
        {appId}
      </button>
    );

    cursor = startIndex + appId.length;
  });

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return <>{parts}</>;
}

export default function ChatBot({ applicationId, applications = [], onSelectApplication }) {
  const [isOpen, setIsOpen] = useState(false);
  const [scope, setScope] = useState('application');
  const [messages, setMessages] = useState([
    { sender: 'assistant', text: 'Hello! I can answer questions about the selected application or the whole portfolio. How can I help?' }
  ]);
  const [inputMsg, setInputMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const selectedAppId = scope === 'application' ? applicationId : null;

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMsg.trim()) return;

    if (scope === 'application' && !selectedAppId) {
      setMessages((prev) => [
        ...prev,
        { sender: 'assistant', text: 'Please select an application first before asking a single-app question.' }
      ]);
      return;
    }

    const userQuestion = inputMsg.trim();
    setMessages((prev) => [...prev, { sender: 'user', text: userQuestion }]);
    setInputMsg('');
    setLoading(true);

    try {
      const payload = {
        scope,
        message: userQuestion,
      };

      if (scope === 'application' && selectedAppId) {
        payload.application_id = selectedAppId;
      }

      const res = await axios.post('http://localhost:8000/api/chat', payload);
      setMessages((prev) => [...prev, { sender: 'assistant', text: res.data.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: 'assistant', text: 'Error contacting assistant. Please ensure the backend is running and the correct application is selected.' }
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
            <span>AI Assistant {scope === 'application' ? `(${selectedAppId || 'No App Selected'})` : '(Portfolio Mode)'}</span>
            <button className="chat-close-btn" onClick={() => setIsOpen(false)}>
              <X size={18} />
            </button>
          </div>

          <div className="chat-scope-switch">
            <button
              type="button"
              className={scope === 'global' ? 'scope-btn active' : 'scope-btn'}
              onClick={() => setScope('global')}
            >
              Global Portfolio
            </button>
            <button
              type="button"
              className={scope === 'application' ? 'scope-btn active' : 'scope-btn'}
              onClick={() => setScope('application')}
            >
              Single Application
            </button>
          </div>

          {scope === 'application' && (
            <div className="chat-app-select-wrap">
              <label>Select application</label>
              <select
                value={selectedAppId || ''}
                onChange={(e) => onSelectApplication?.(e.target.value)}
                disabled={!applications.length}
              >
                <option value="">{applications.length ? 'Choose an application' : 'No applications available yet'}</option>
                {applications.map((app) => {
                  const appId = app.application_id || app.applicant_id || 'N/A';
                  const applicantName = app.applicant_name || 'Applicant';
                  return (
                    <option key={appId} value={appId}>
                      {appId} - {applicantName}
                    </option>
                  );
                })}
              </select>
            </div>
          )}

          <div className="chat-messages">
            {messages.map((m, idx) => (
              <div key={idx} className={`chat-msg ${m.sender}`}>
                {m.sender === 'assistant'
                  ? renderMessageWithBadges(m.text, onSelectApplication)
                  : m.text}
              </div>
            ))}
            {loading && <div className="chat-msg assistant">Thinking...</div>}
          </div>

          <form className="chat-input-form" onSubmit={sendMessage}>
            <input
              type="text"
              placeholder={
                scope === 'application'
                  ? selectedAppId
                    ? 'Ask about this application...'
                    : 'Select an application first'
                  : 'Ask about the whole portfolio...'
              }
              value={inputMsg}
              disabled={(scope === 'application' && !selectedAppId) || loading}
              onChange={(e) => setInputMsg(e.target.value)}
            />
            <button type="submit" disabled={(scope === 'application' && !selectedAppId) || loading}>
              <Send size={14} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}