import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import IngestPage   from './pages/IngestPage';
import ChatPage     from './pages/ChatPage';
import WikiPage     from './pages/WikiPage';
import AuditPage    from './pages/AuditPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/"         element={<IngestPage />} />
            <Route path="/chat"     element={<ChatPage />} />
            <Route path="/wiki"     element={<WikiPage />} />
            <Route path="/audit"    element={<AuditPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  );
}
