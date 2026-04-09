import './globals.css';

export const metadata = {
  title: 'SRS Maker Agent — IEEE SRS Generator',
  description: 'Multimodal IEEE SRS document generator · MiniCPM-O 4.5 + DeepSeek V3',
  icons: { icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌐</text></svg>" },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </head>
      <body style={{ background: '#03030F', minHeight: '100vh' }}>
        {children}
      </body>
    </html>
  );
}
