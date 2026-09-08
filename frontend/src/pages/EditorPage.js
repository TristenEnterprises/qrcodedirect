import Designer from "./Designer";

export default function EditorPage() {
  return (
    <main className="wrap" style={{ paddingTop: 28, paddingBottom: 90 }}>
      <Designer initial={null} />
    </main>
  );
}
