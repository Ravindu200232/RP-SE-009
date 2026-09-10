import { createTheme, CssBaseline, ThemeProvider } from '@mui/material';
const theme = createTheme({ shape: { borderRadius: 12 }, palette: { mode: 'light', primary: { main: '#4f46e5' }, background: { default: '#f8fafc', paper: '#fff' } }, typography: { fontFamily: 'Inter, "Segoe UI", sans-serif', h1: { fontWeight: 700, letterSpacing: '-0.04em' } } });
export function Provider({ children }) { return <ThemeProvider theme={theme}><CssBaseline />{children}</ThemeProvider>; }
