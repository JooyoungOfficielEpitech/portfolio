import { useState, useRef, useEffect } from 'react';
import './App.css';

interface Message {
  content: string;
  type: 'user' | 'bot';
  timestamp: Date;
}

interface QuickButton {
  label: string;
  query: string;
}

interface UserInfo {
  organization: string;
}

const quickButtons: QuickButton[] = [
  { label: '기술 스택', query: '보유하고 계신 기술 스택을 알려주세요.' },
  { label: '프로젝트 경험', query: '주요 프로젝트 경험에 대해 설명해주세요.' },
  { label: '학력', query: '학력 사항을 알려주세요.' },
  { label: '경력', query: '경력 사항을 알려주세요.' },
  { label: '자격증', query: '보유하신 자격증을 알려주세요.' }
];

const API_URL = import.meta.env.VITE_API_URL;

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      content: "안녕하세요! 저는 당신의 이력서를 소개해드릴 챗봇입니다. 어떤 것이 궁금하신가요?",
      type: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(() => {
    const savedInfo = localStorage.getItem('userInfo');
    return savedInfo ? JSON.parse(savedInfo) : null;
  });
  const [showUserModal, setShowUserModal] = useState(!userInfo);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const organizationInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleUserSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const organization = organizationInputRef.current?.value.trim();
    
    if (!organization) {
      alert('소속을 입력해주세요.');
      return;
    }

    const newUserInfo = { organization };
    setUserInfo(newUserInfo);
    localStorage.setItem('userInfo', JSON.stringify(newUserInfo));
    setShowUserModal(false);
  };

  const handleLogout = () => {
    setUserInfo(null);
    localStorage.removeItem('userInfo');
    setShowUserModal(true);
  };

  const handleSend = async (text: string = inputText) => {
    if (text.trim() === '' || !userInfo) return;
    setIsLoading(true);

    const userMessage = {
      content: text,
      type: 'user' as const,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText('');

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: userInfo.organization,
          query: userMessage.content,
          user_info: userInfo
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error('응답 실패');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');

      let botMessage = '';
      setMessages((prev) => [
        ...prev,
        {
          content: botMessage,
          type: 'bot',
          timestamp: new Date(),
        },
      ]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        botMessage += decoder.decode(value, { stream: true });

        setMessages((prev) => [
          ...prev.slice(0, -1),
          {
            content: botMessage,
            type: 'bot',
            timestamp: new Date(),
          },
        ]);
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages((prev) => [
        ...prev,
        {
          content: '죄송합니다. 서버와 연결할 수 없습니다.',
          type: 'bot',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickButtonClick = (query: string) => {
    if (!isLoading && userInfo) {
      handleSend(query);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>이력서 챗봇</h1>
        {userInfo && (
          <div className="user-info">
            <span>{userInfo.organization}</span>
            <button onClick={handleLogout} className="logout-button">로그아웃</button>
          </div>
        )}
      </div>

      {showUserModal && (
        <div className="modal-overlay">
          <div className="user-modal">
            <h2>사용자 정보 입력</h2>
            <form onSubmit={handleUserSubmit}>
              <div className="input-group">
                <label htmlFor="organization">소속</label>
                <input
                  type="text"
                  id="organization"
                  ref={organizationInputRef}
                  placeholder="소속을 입력하세요"
                  required
                />
              </div>
              <button type="submit">시작하기</button>
            </form>
          </div>
        </div>
      )}

      <div className="messages-container">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`message ${
              message.type === 'user' ? 'user-message' : 'bot-message'
            }`}
          >
            <div className="message-content">{message.content}</div>
            <div className="message-timestamp">
              {message.timestamp.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="quick-buttons-container">
        {quickButtons.map((button, index) => (
          <button
            key={index}
            onClick={() => handleQuickButtonClick(button.query)}
            disabled={isLoading || !userInfo}
            className="quick-button"
          >
            {button.label}
          </button>
        ))}
      </div>

      <div className="input-container">
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={userInfo ? "메시지를 입력하세요..." : "사용자 정보를 먼저 입력해주세요"}
          rows={1}
          disabled={isLoading || !userInfo}
        />
        <button 
          onClick={() => handleSend()} 
          disabled={!inputText.trim() || isLoading || !userInfo}
        >
          전송
        </button>
      </div>
    </div>
  );
}

export default App;