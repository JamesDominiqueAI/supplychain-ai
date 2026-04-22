export default function ServerErrorPage() {
  return (
    <main className="page shell">
      <section className="panel">
        <p className="eyebrow">500</p>
        <h1>Something went wrong.</h1>
        <p className="lede">The application hit an unexpected error. Try again in a moment.</p>
      </section>
    </main>
  );
}
