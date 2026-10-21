export const environment = {
  production: true,
  // Em produção, usa URLs relativas ao mesmo domínio se servido junto, ou a URL configurada
  apiUrl: (typeof window !== 'undefined' && (window as any).__ENV?.API_URL) || ''
};
