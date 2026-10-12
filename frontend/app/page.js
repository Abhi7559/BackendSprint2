export default function HomePage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  return (
    <main style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          padding: '1rem 2rem',
          background: '#0f172a',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.25rem', margin: 0, fontWeight: 700, color: '#f8fafc' }}>
            Staff Portal <span style={{ fontSize: '0.85rem', color: '#818cf8', fontWeight: 500 }}>(Next.js Shell)</span>
          </h1>
          <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
            Integration companion embedding server-rendered HTMX view
          </p>
        </div>
        <div style={{ fontSize: '0.8rem', color: '#64748b', background: '#1e293b', padding: '0.35rem 0.75rem', borderRadius: '0.5rem' }}>
          Source: {apiUrl}/ui/films
        </div>
      </header>

      <section style={{ flex: 1, position: 'relative', width: '100%', minHeight: 'calc(100vh - 70px)' }}>
        <iframe
          src={`${apiUrl}/ui/films`}
          title="Server-Rendered Film Search"
          style={{
            width: '100%',
            height: '100%',
            minHeight: '85vh',
            border: 'none',
            display: 'block',
          }}
        />
      </section>
    </main>
  );
}
