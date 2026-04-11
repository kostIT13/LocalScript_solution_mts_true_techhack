// frontend/src/App.tsx

import React, { useState, useRef, useEffect } from 'react';
import { apiClient } from './services/api';
import { authService } from './services/auth';  // 🔹 Импорт
import AuthPage from './pages/AuthPage';  // 🔹 Импорт
import UploadPage from './pages/uploadPage';
import type { ChatMessage, DoneMessage } from './types';
import './index.css';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(authService.isAuthenticated());
  const [currentPage, setCurrentPage] = useState<'chat' | 'upload'>('chat');
  const [currentUser, setCurrentUser] = useState(authService.getCachedUser());
  
  // ...остальные стейты (task, messages, и т.д.)...
  const [task, setTask] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentCode, setCurrentCode] = useState('');
  const [temperature, setTemperature] = useState(0.1);
  const [runTest, setRunTest] = useState(true);
  const [useRag, setUseRag] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [mode, setMode] = useState<'simple' | 'rag'>('simple');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentCode]);

  useEffect(() => {
    setUseRag(mode === 'rag');
  }, [mode]);

  // 🔹 Обработчик успешной аутентификации
  const handleAuthenticated = () => {
    setIsAuthenticated(true);
    setCurrentUser(authService.getCachedUser());
  };

  // 🔹 Logout
  const handleLogout = () => {
    authService.logout();
    setIsAuthenticated(false);
    setCurrentUser(null);
  };

  // ...остальные функции (handleGenerate, handleFeedbackSubmit, и т.д.)...
  const handleGenerate = async () => {
    if (!task.trim() && !feedback.trim()) return;
    if (isLoading) return;

    setIsLoading(true);
    setCurrentCode('');

    const isFeedback = feedback.trim() && chatId;
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: isFeedback ? `💬 Уточнение: ${feedback}` : task,
      timestamp: new Date(),
    };

    const assistantMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);

    await apiClient.generateLua(
      {
        task: task || 'Продолжи предыдущий код',
        temperature,
        user_id: currentUser?.id || 'dev-user-temp',
        run_test: runTest,
        use_rag: useRag,
        chat_id: chatId,
        feedback: isFeedback ? feedback : null,
      },
      (token) => {
        setCurrentCode(prev => prev + token);
        setMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (updated[lastIdx]?.role === 'assistant') {
            updated[lastIdx] = { 
              ...updated[lastIdx], 
              content: updated[lastIdx].content + token 
            };
          }
          return updated;
        });
      },
      (done: DoneMessage) => {
        console.log('✅ Generation complete:', done);
        setChatId(done.chat_id);
        setMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (updated[lastIdx]?.role === 'assistant') {
            updated[lastIdx] = {
              ...updated[lastIdx],
              code: done.code,
              sandbox_result: done.sandbox_result,
              rag: done.rag,
              timing_ms: done.timing_ms,
            };
          }
          return updated;
        });
        setCurrentCode('');
        setIsLoading(false);
        setTask('');
        setFeedback('');
      },
      (error) => {
        setMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (updated[lastIdx]?.role === 'assistant') {
            updated[lastIdx] = { 
              ...updated[lastIdx], 
              content: `❌ Ошибка: ${error}` 
            };
          }
          return updated;
        });
        setIsLoading(false);
      },
      useRag
    );

    if (!isFeedback) {
      setTask('');
    }
  };

  const handleFeedbackSubmit = async () => {
    console.log('📤 Feedback submit:', { feedback, chatId });
    if (!feedback.trim()) return;
    await handleGenerate();
  };

  const handleNewChat = () => {
    setChatId(null);
    setMessages([]);
    setFeedback('');
    setTask('');
  };

  const canShowFeedback = messages.some(m => m.role === 'assistant' && m.code);

  const renderNav = () => (
    <nav className="main-nav">
      <div className="nav-left">
        <button
          className={`nav-btn ${currentPage === 'chat' ? 'active' : ''}`}
          onClick={() => setCurrentPage('chat')}
        >
          💬 Чат
        </button>
        <button
          className={`nav-btn ${currentPage === 'upload' ? 'active' : ''}`}
          onClick={() => setCurrentPage('upload')}
        >
          📚 Документы
        </button>
      </div>
      <div className="nav-right">
        {currentUser && (
          <span className="user-info">👤 {currentUser.email}</span>
        )}
        <button onClick={handleLogout} className="btn-logout">
          🚪 Выход
        </button>
      </div>
    </nav>
  );

  const renderChat = () => (
    <>
      <header className="header">
        <div>
          <h1>🤖 LocalScript AI</h1>
          <p>Генерация Lua-кода {mode === 'rag' ? 'с RAG' : '(быстрый режим)'}</p>
        </div>
        
        <div className="mode-switcher">
          <button
            className={`mode-btn ${mode === 'simple' ? 'active' : ''}`}
            onClick={() => setMode('simple')}
          >
            ⚡ Простой
          </button>
          <button
            className={`mode-btn ${mode === 'rag' ? 'active' : ''}`}
            onClick={() => setMode('rag')}
          >
            📚 С RAG
          </button>
        </div>
        
        <button onClick={handleNewChat} className="btn-new-chat">+ Новый чат</button>
      </header>

      <div className={`mode-indicator ${mode}`}>
        {mode === 'rag' ? '📚 Режим с базой знаний (RAG)' : '⚡ Быстрый режим (без RAG)'}
      </div>

      {/* ...остальной код чата (messages, settings, input-area)... */}
      <div className="main">
        <div className="chat-container">
          <div className="messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-header">
                  <span className="role">{msg.role === 'user' ? '👤 Вы' : '🤖 Агент'}</span>
                  <span className="time">{msg.timestamp.toLocaleTimeString()}</span>
                </div>
                
                {msg.role === 'user' ? (
                  <div className="message-content">{msg.content}</div>
                ) : (
                  <>
                    {msg.code ? (
                      <pre className="code-block"><code>{msg.code}</code></pre>
                    ) : (
                      <div className="message-content">{msg.content || currentCode}</div>
                    )}
                    
                    {msg.rag && msg.rag.used && (
                      <div className="rag-section">
                        <h4>📚 Источники RAG</h4>
                        {msg.rag.sources.map((source, i) => (
                          <div key={i} className="rag-source">
                            <strong>{source.filename}</strong>
                            <span className="score">Score: {source.score.toFixed(3)}</span>
                            <p>{source.preview}...</p>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {msg.sandbox_result && (
                      <div className={`sandbox-result ${msg.sandbox_result.success ? 'success' : 'error'}`}>
                        <h4>🧪 Sandbox</h4>
                        <div className="sandbox-info">
                          <span>Status: {msg.sandbox_result.success ? '✅ Success' : '❌ Failed'}</span>
                          {msg.sandbox_result.output && (
                            <span>Output: <code>{msg.sandbox_result.output}</code></span>
                          )}
                          {msg.sandbox_result.error && (
                            <span>Error: {msg.sandbox_result.error}</span>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {msg.timing_ms && <div className="timing">⏱ {msg.timing_ms}ms</div>}
                  </>
                )}
              </div>
            ))}
            
            {isLoading && !currentCode && (
              <div className="message assistant">
                <div className="loading">⏳ Генерация...</div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {canShowFeedback && (
            <div className="feedback-section">
              <input
                type="text"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="💬 Уточните или попросите улучшить код..."
                onKeyPress={(e) => e.key === 'Enter' && handleFeedbackSubmit()}
              />
              <button 
                onClick={handleFeedbackSubmit} 
                disabled={!feedback.trim() || isLoading}
              >
                {isLoading ? '⏳...' : 'Отправить'}
              </button>
            </div>
          )}
        </div>

        <aside className="settings-panel">
          <h3>⚙️ Настройки</h3>
          <div className="setting">
            <label>Temperature: {temperature}</label>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))} 
            />
          </div>
          <div className="setting">
            <label>
              <input 
                type="checkbox" 
                checked={runTest} 
                onChange={(e) => setRunTest(e.target.checked)} 
              />
              🧪 Запускать в Sandbox
            </label>
          </div>
          <div className="setting">
            <label>
              <input 
                type="checkbox" 
                checked={useRag} 
                onChange={(e) => {
                  setUseRag(e.target.checked);
                  setMode(e.target.checked ? 'rag' : 'simple');
                }} 
              />
              📚 Использовать RAG
            </label>
          </div>
          <div className="setting">
            <label>Chat ID: {chatId ? chatId.slice(0, 8) + '...' : 'Нет'}</label>
          </div>
          
          <div className="mode-info">
            {mode === 'rag' ? (
              <p className="info-text">
                📚 <strong>RAG режим:</strong> ищет в базе знаний Lua-документации
              </p>
            ) : (
              <p className="info-text">
                ⚡ <strong>Простой режим:</strong> быстрая генерация без поиска
              </p>
            )}
          </div>
        </aside>
      </div>

      <div className="input-area">
        <input
          type="text"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Опишите задачу на естественном языке..."
          onKeyPress={(e) => e.key === 'Enter' && handleGenerate()}
          disabled={isLoading}
        />
        <button onClick={handleGenerate} disabled={isLoading || (!task.trim() && !feedback.trim())}>
          {isLoading ? '⏳ Генерация...' : `🚀 Генерировать ${mode === 'rag' ? '(RAG)' : ''}`}
        </button>
      </div>
    </>
  );

  // 🔹 Если не авторизован — показываем AuthPage
  if (!isAuthenticated) {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  // 🔹 Если авторизован — показываем приложение
  return (
    <div className="app">
      {renderNav()}
      {currentPage === 'chat' ? renderChat() : <UploadPage />}
    </div>
  );
}