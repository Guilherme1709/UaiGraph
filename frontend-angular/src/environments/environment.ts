export const environment = {
  production: false,
  // Em desenvolvimento, aponta para a API FastAPI local
  apiUrl: (typeof window !== 'undefined' && (window as any).__ENV?.API_URL) || 'http://localhost:8000'
};
