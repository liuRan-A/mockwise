import http from './http'

export const groupApi = {
  detail: (sessionId) => http.get(`/group/sessions/${sessionId}`),
  raise: (sessionId, payload) => http.post(`/group/sessions/${sessionId}/raise`, payload),
}
