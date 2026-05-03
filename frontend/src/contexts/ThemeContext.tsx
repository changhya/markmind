import { createContext, useContext, useState, useEffect } from 'react';

interface ThemeCtx { dark: boolean; toggle: () => void }

const ThemeContext = createContext<ThemeCtx>({ dark: true, toggle: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [dark, setDark] = useState(
    () => localStorage.getItem('markmind_theme') !== 'light'
  );

  useEffect(() => {
    localStorage.setItem('markmind_theme', dark ? 'dark' : 'light');
  }, [dark]);

  return (
    <ThemeContext.Provider value={{ dark, toggle: () => setDark((d) => !d) }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
