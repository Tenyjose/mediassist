import React, { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';

const CONVERSATION_API = process.env.REACT_APP_CONVERSATION_API || 'http://localhost:8002';

const WELCOME_MESSAGE = {
  role: 'assistant',
  text: 'Hello! I\'m MediAssist, your City General Hospital appointment assistant. I can help you view or cancel appointments, and answer questions about our services.\n\nHow can I help you today?',
};

export default function App() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('mediassist_sid') || null);
  const textareaRef = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isTyping) return;

    setMessages(prev => [...prev, { role: 'user', text }]);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setIsTyping(true);

    try {
      const res = await fetch(`${CONVERSATION_API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
        localStorage.setItem('mediassist_sid', data.session_id);
      }

      setMessages(prev => [...prev, { role: 'assistant', text: data.response }]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', text: 'I\'m sorry, I couldn\'t connect to the server. Please try again in a moment.' },
      ]);
    } finally {
      setIsTyping(false);
    }
  }, [input, isTyping, sessionId]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetSession = () => {
    localStorage.removeItem('mediassist_sid');
    setSessionId(null);
    setMessages([WELCOME_MESSAGE]);
    setInput('');
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="header-icon">🏥</div>
          <div className="header-text">
            <h1>MediAssist</h1>
            <span>City General Hospital · AI Appointment Assistant</span>
          </div>
        </div>
        <button className="reset-btn" onClick={resetSession} title="Start new conversation">
          New Chat
        </button>
      </header>

      <main className="chat-window">
        {messages.map((msg, i) => (
          <div key={i} className={`bubble-row ${msg.role}`}>
            {msg.role === 'assistant' && <div className="avatar">🏥</div>}
            <div className={`bubble ${msg.role}`}>
              {msg.text.split('\n').map((line, j, arr) => (
                <span key={j}>
                  {line}
                  {j < arr.length - 1 && <br />}
                </span>
              ))}
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="bubble-row assistant">
            <div className="avatar">🏥</div>
            <div className="bubble assistant typing">
              <span /><span /><span />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <footer className="input-area">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => { setInput(e.target.value); autoResize(); }}
          onKeyDown={handleKey}
          placeholder="Type your message… (Enter to send, Shift+Enter for new line)"
          rows={1}
          disabled={isTyping}
        />
        <button
          className="send-btn"
          onClick={sendMessage}
          disabled={isTyping || !input.trim()}
          aria-label="Send message"
        >
          ➤
        </button>
      </footer>
    </div>
  );
}
