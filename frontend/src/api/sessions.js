import http from './http'

export const sessionApi = {
  create: (payload) => http.post('/sessions', payload),
  get: (sessionId) => http.get(`/sessions/${sessionId}`),
  submitAnswer: (sessionId, sqId, payload) =>
    http.post(`/sessions/${sessionId}/questions/${sqId}/answer`, payload),
  finish: (sessionId) => http.post(`/sessions/${sessionId}/finish`),
  questionDetail: (sessionId, sqId) =>
    http.get(`/sessions/${sessionId}/questions/${sqId}`),
  feedback: (sqId, payload) =>
    http.post(`/sessions/questions/${sqId}/feedback`, payload),
  peers: (sessionId) => http.get(`/sessions/${sessionId}/peers`),
  peerTalk: (sessionId, payload) =>
    http.post(`/sessions/${sessionId}/peer-talk`, payload),
  groupRound: (sessionId, payload) =>
    http.post(`/sessions/${sessionId}/round`, payload),
}
