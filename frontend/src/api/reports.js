import http from './http'

export const reportApi = {
  list: (limit = 20) => http.get('/reports', { params: { limit } }),
  detail: (reportId) => http.get(`/reports/${reportId}`),
  bySession: (sessionId) => http.get(`/reports/by-session/${sessionId}`),
}
