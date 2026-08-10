export default function BotsPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Bots</h1>
        <button className="btn btn-primary">+ Nuevo bot</button>
      </div>
      <div className="card bg-base-200">
        <div className="card-body text-center opacity-70">
          Aún no hay bots. Crea uno para empezar.
        </div>
      </div>
    </div>
  );
}
