import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../api';
import { MessageSquare, Mic, MicOff, Plus, Square, Trash2, X, Send } from 'lucide-react';
import { createChat, loadChatState, removeChat, saveChatState, updateChat } from './chatHistory';
import { createChatSpeech } from './chatSpeech';

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
  const [chatState, setChatState] = useState(() => loadChatState(applicationId || null));
  const [inputMsg, setInputMsg] = useState('');
  const [loadingChatIds, setLoadingChatIds] = useState([]);
  const [hasVoiceInput, setHasVoiceInput] = useState(false);
  const [speechState, setSpeechState] = useState({ listening: false, speaking: false });
  const [speechError, setSpeechError] = useState('');
  const [speech] = useState(() => createChatSpeech({
    onTranscript: (text) => {
      setInputMsg(text);
      setHasVoiceInput(true);
    },
    onState: setSpeechState,
    onError: setSpeechError,
  }));
  const triggerRef = useRef(null);
  const newChatRef = useRef(null);
  const inputRef = useRef(null);
  const messagesRef = useRef(null);
  const inFlight = useRef(new Map());
  const previousApplicationId = useRef(applicationId);
  const { chats, activeChatId, storageError, persistenceEnabled } = chatState;
  const activeChat = chats.find((chat) => chat.id === activeChatId);
  const loading = loadingChatIds.includes(activeChatId);
  const selectedAppId = activeChat.applicationId;
  const recentChats = chats.filter((chat) => chat.messages.some((message) => message.sender === 'user'));

  useEffect(() => {
    speech.cancel();
    setHasVoiceInput(false);
    setSpeechError('');
    if (isOpen) {
      try {
        window.speechSynthesis?.getVoices();
      } catch {
        setSpeechError('The browser voice list could not be loaded. Written chat is still available.');
      }
    }
    return () => speech.cancel();
  }, [activeChatId, isOpen, speech]);

  const closeChat = () => {
    speech.cancel();
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!persistenceEnabled) return;
    try {
      saveChatState(chats, activeChatId);
      setChatState((previous) => previous.storageError ? { ...previous, storageError: '' } : previous);
    } catch {
      console.error('Chat history could not be saved in this browser.');
      setChatState((previous) => ({
        ...previous,
        storageError: 'These changes could not be saved in this browser. Keep this page open to retain them.',
      }));
    }
  }, [chats, activeChatId, persistenceEnabled]);

  useEffect(() => {
    if (previousApplicationId.current === applicationId) return;
    previousApplicationId.current = applicationId;
    setChatState((previous) => ({
      ...previous,
      chats: updateChat(previous.chats, previous.activeChatId, (chat) => ({
        ...chat, applicationId: applicationId || null,
      })),
    }));
  }, [applicationId]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [activeChatId, isOpen]);

  useEffect(() => {
    if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, [activeChatId, activeChat.messages.length, loading, isOpen]);

  const startNewChat = () => {
    speech.cancel();
    const newChat = createChat();
    setChatState((previous) => ({
      ...previous,
      activeChatId: newChat.id,
      chats: [newChat, ...previous.chats.filter((chat) => chat.messages.some((message) => message.sender === 'user'))],
    }));
    setInputMsg('');
    onSelectApplication?.('');
  };

  const openChat = (chat) => {
    speech.cancel();
    setHasVoiceInput(false);
    setChatState((previous) => ({ ...previous, activeChatId: chat.id }));
    setInputMsg('');
    onSelectApplication?.(chat.applicationId || '');
  };

  const deleteChat = (chatId) => {
    const replacement = chats.find((chat) => chat.id !== chatId) || createChat();
    inFlight.current.get(chatId)?.abort();
    setChatState((previous) => removeChat(previous, chatId, replacement));
    if (chatId === activeChatId) {
      speech.cancel();
      setInputMsg('');
      onSelectApplication?.(replacement.applicationId || '');
    }
    newChatRef.current?.focus();
  };

  const selectApplication = (id) => {
    speech.cancel();
    setChatState((previous) => ({
      ...previous,
      chats: updateChat(previous.chats, previous.activeChatId, (chat) => ({
        ...chat, applicationId: id || null,
      })),
    }));
    onSelectApplication?.(id);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMsg.trim() || inFlight.current.has(activeChatId) || speechState.listening) return;

    const requestChatId = activeChatId;
    const userQuestion = inputMsg.trim();
    const speakReply = hasVoiceInput;
    speech.cancel();
    const speechSession = speech.sessionId;
    setHasVoiceInput(false);
    const controller = new AbortController();
    inFlight.current.set(requestChatId, controller);
    setLoadingChatIds((previous) => [...previous, requestChatId]);
    setChatState((previous) => controller.signal.aborted ? previous : ({
      ...previous,
      chats: updateChat(previous.chats, requestChatId, (chat) => ({
        ...chat,
        title: chat.messages.some((message) => message.sender === 'user') ? chat.title : userQuestion.slice(0, 60),
        updatedAt: Date.now(),
        messages: [...chat.messages, { sender: 'user', text: userQuestion }],
      }), true),
    }));
    setInputMsg('');

    try {
      const payload = {
        scope: 'general',
        message: userQuestion,
        history: activeChat.history,
      };

      if (selectedAppId) {
        payload.application_id = selectedAppId;
      }

      const res = await axios.post(`${API_BASE_URL}/api/chat`, payload, { signal: controller.signal });
      if (controller.signal.aborted) return;
      if (typeof res.data.reply !== 'string' || !res.data.reply.trim() || res.data.reply.length > 16000) {
        throw new Error('Invalid assistant response');
      }
      setChatState((previous) => controller.signal.aborted ? previous : ({
        ...previous,
        chats: updateChat(previous.chats, requestChatId, (chat) => ({
          ...chat,
          messages: [...chat.messages, { sender: 'assistant', text: res.data.reply, language: 'en' }],
          history: [...chat.history, { user_msg: userQuestion, assistant_msg: res.data.reply }].slice(-6),
        })),
      }));
      if (speakReply) speech.speak(res.data.reply, speechSession);
    } catch (err) {
      if (controller.signal.aborted) return;
      console.error('Chat request failed:', err.response?.status || 'Network error');
      setChatState((previous) => controller.signal.aborted ? previous : ({
        ...previous,
        chats: updateChat(previous.chats, requestChatId, (chat) => ({
          ...chat,
          messages: [...chat.messages, {
            sender: 'assistant', text: 'The assistant is temporarily unavailable. Please try again.', error: true,
          }],
        })),
      }));
    } finally {
      inFlight.current.delete(requestChatId);
      setLoadingChatIds((previous) => previous.filter((id) => id !== requestChatId));
    }
  };

  return (
    <>
      <button ref={triggerRef} className="floating-chat-trigger" aria-label={isOpen ? 'Close assistant' : 'Open assistant'} aria-expanded={isOpen} aria-controls="assistant-panel" onClick={() => isOpen ? closeChat() : setIsOpen(true)}>
        <MessageSquare size={22} aria-hidden="true" />
      </button>

      {isOpen && (
        <section id="assistant-panel" className="chat-modal" aria-label="AI assistant" onKeyDown={(event) => {
          if (event.key === 'Escape') {
            closeChat();
          }
        }}>
          <div className="chat-header">
            <span>AI Assistant</span>
            <button className="chat-close-btn" aria-label="Close assistant" onClick={closeChat}>
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          {storageError && <p className="chat-storage-error" role="alert">{storageError}</p>}
          <div className="chat-workspace">
            <nav className="chat-history-panel" aria-label="Chat history">
              <button ref={newChatRef} type="button" className="chat-new-button" onClick={startNewChat}>
                <Plus size={16} aria-hidden="true" />
                New chat
              </button>
              <h2 id="recent-chats-heading">Recent chats</h2>
              <ul className="chat-recent-list" aria-labelledby="recent-chats-heading">
                {recentChats.map((chat) => (
                  <li key={chat.id} className="chat-recent-item">
                    <button
                      type="button"
                      className="chat-recent-button"
                      aria-current={chat.id === activeChatId ? 'true' : undefined}
                      title={chat.title}
                      onClick={() => openChat(chat)}
                    >
                      <MessageSquare size={14} aria-hidden="true" />
                      <span>{chat.title}</span>
                    </button>
                    <button
                      type="button"
                      className="chat-delete-button"
                      aria-label={`Delete chat: ${chat.title}`}
                      title="Delete chat"
                      onClick={() => deleteChat(chat.id)}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
              {!recentChats.length && <p className="chat-history-empty">Your conversations will appear here.</p>}
            </nav>
            <div className="chat-conversation">
          <div className="chat-app-select-wrap">
              <label htmlFor="chat-application">Select application (optional)</label>
              <select
                id="chat-application"
                value={selectedAppId || ''}
                onChange={(e) => selectApplication(e.target.value)}
                disabled={!applications.length}
              >
                <option value="">{applications.length ? 'Choose an application (optional)' : 'No applications yet - general chat is available'}</option>
                {selectedAppId && !applications.some((app) => (app.application_id || app.applicant_id) === selectedAppId) && (
                  <option value={selectedAppId}>{selectedAppId} (saved selection)</option>
                )}
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

          <div ref={messagesRef} className="chat-messages" role="log" aria-label="Conversation" aria-live="polite">
            {activeChat.messages.map((m, idx) => (
              <div key={idx} className={`chat-msg ${m.sender}`} dir="auto" lang={m.language || undefined} role={m.error ? 'alert' : undefined}>
                {m.sender === 'assistant'
                  ? renderMessageWithBadges(m.text, selectApplication)
                  : m.text}
              </div>
            ))}
            {loading && <div className="chat-msg assistant">Thinking...</div>}
          </div>

          {speechState.speaking && (
            <div className="chat-voice-controls">
              <button
                type="button"
                onClick={() => {
                  speech.cancel();
                  inputRef.current?.focus();
                }}
              >
                <Square size={14} aria-hidden="true" />
                Stop audio
              </button>
            </div>
          )}
          {speechError && <p className="chat-voice-error" role="alert">{speechError}</p>}
          <div className="chat-voice-status" role="status">
            {speechState.listening ? 'Listening... Tap the microphone again to finish.' : speechState.speaking ? 'Reading reply aloud...' : ''}
          </div>
          <form className="chat-input-form" onSubmit={sendMessage}>
            <input
              ref={inputRef}
              type="text"
              dir="auto"
              aria-label="Message to assistant"
              maxLength={4000}
              placeholder="Ask about applications, portfolio, or any topic..."
              value={inputMsg}
              disabled={loading}
              readOnly={speechState.listening}
              onChange={(e) => {
                setInputMsg(e.target.value);
                if (!e.target.value.trim()) setHasVoiceInput(false);
              }}
            />
            <button
              type="button"
              className="chat-microphone-button"
              aria-label={speechState.listening ? 'Stop voice input' : 'Start voice input'}
              aria-pressed={speechState.listening}
              disabled={loading}
              onClick={() => speechState.listening ? speech.stopListening() : speech.startListening(inputMsg)}
            >
              {speechState.listening ? <MicOff size={16} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />}
            </button>
            <button type="submit" aria-label="Send message" disabled={!inputMsg.trim() || loading || speechState.listening}>
              <Send size={14} aria-hidden="true" />
            </button>
          </form>
            </div>
          </div>
        </section>
      )}
    </>
  );
}