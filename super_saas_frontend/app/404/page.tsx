export default function TenantNotFoundPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-6 text-center">
      <h1 className="text-3xl font-semibold">Tenant não encontrado</h1>
      <p className="mt-3 text-sm text-slate-600">
        O subdomínio informado não está vinculado a nenhum workspace ativo.
      </p>
    </main>
  );
}
