export const metadata = {
  title: 'Film Catalogue - Staff Portal',
  description: 'Companion Next.js portal embedding the HTMX server-rendered film view',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0, background: '#090d16', color: '#f8fafc', fontFamily: 'sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
