import { useState } from 'react'
import axios from 'axios'
import './index.css'

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<{role: string, content: string}[]>([]);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      const res = await axios.post("http://127.0.0.1:8000/api/upload", formData);
      alert(`Upload Success! Chunks stored: ${res.data.chunks_count}`);
      setFile(null);
    } catch (error) {
      console.error(error);
      alert("Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async () => {
    if (!query.trim()) return;

    const userMessage = { role: "user", content: query };
    setMessages(prev => [...prev, userMessage]);
    setQuery("");
    setLoading(true);

    try {
      const res = await axios.post("http://127.0.0.1:8000/api/chat", { query });
      const botMessage = { role: "bot", content: res.data.response };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error(error);
      const errorMessage = { role: "bot", content: "Error communicating with server." };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>MarkMind - Local Edge AI</h1>
      
      <div className="upload-section">
        <h2>1. Upload Document</h2>
        <input type="file" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={!file || loading}>
          {loading ? "Uploading..." : "Upload & Parse"}
        </button>
      </div>

      <div className="chat-section">
        <h2>2. Chat with your Data (RAG)</h2>
        <div className="chat-box">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <strong>{msg.role === "user" ? "You" : "MarkMind"}: </strong>
              <span>{msg.content}</span>
            </div>
          ))}
        </div>
        <div className="input-box">
          <input 
            type="text" 
            value={query} 
            onChange={(e) => setQuery(e.target.value)} 
            onKeyDown={(e) => e.key === 'Enter' && handleChat()}
            placeholder="Ask a question about the document..."
          />
          <button onClick={handleChat} disabled={!query.trim() || loading}>
            {loading ? "Thinking..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
