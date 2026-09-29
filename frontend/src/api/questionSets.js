import http from './http'

export const questionSetApi = {
  list: (params) => http.get('/question-sets', { params }),
  detail: (setId) => http.get(`/question-sets/${setId}`),
}
