import http from './http'

export const dashboardApi = {
  get: () => http.get('/dashboard'),
  trend: (limit = 5) => http.get('/dashboard/trend', { params: { limit } }),
  recommend: (limit = 3) => http.get('/dashboard/recommend', { params: { limit } }),
  history: (limit = 5) => http.get('/dashboard/history', { params: { limit } }),
  formStats: () => http.get('/dashboard/form-stats'),
}
