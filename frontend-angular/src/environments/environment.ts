export const environment = {
  production: false,
  apiUrl: (typeof window !== 'undefined' && (window as any).__ENV?.API_URL) || 'http://localhost:8000'
};
