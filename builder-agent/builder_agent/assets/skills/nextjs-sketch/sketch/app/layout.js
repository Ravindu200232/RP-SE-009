export const metadata = {
  title: 'Sketch storefront',
  description: 'The smallest Next.js + MongoDB application that is actually complete.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
