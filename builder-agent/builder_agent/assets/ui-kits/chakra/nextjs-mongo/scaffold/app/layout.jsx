import './globals.css';
import { Provider } from '@/components/ui/provider.jsx';
export const metadata = { title: 'Application', description: 'Replace this metadata with the application’s own.' };
export default function RootLayout({ children }) { return <html lang="en" suppressHydrationWarning><body><Provider>{children}</Provider></body></html>; }
