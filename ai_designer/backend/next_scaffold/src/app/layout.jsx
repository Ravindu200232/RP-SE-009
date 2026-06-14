import './globals.css';
import '../theme.css';
import Inspector from '@/components/Inspector';

// __FONTS_LINK__ and metadata are rewritten per project by the generator.
export const metadata = {
  title: '__APP_TITLE__',
  description: '__APP_DESCRIPTION__',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="__FONTS_URL__" rel="stylesheet" />
        <link rel="icon" href="/assets/logo.jpg" />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased __PARADIGM_CLASS__">
        {children}
        <Inspector />
      </body>
    </html>
  );
}
