import http from './http'

export const resumeApi = {
  upload: (formData) =>
    http.post('/resumes/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    }),
  list: () => http.get('/resumes'),
  active: () => http.get('/resumes/active'),
  activate: (id) => http.post(`/resumes/${id}/activate`),
  remove: (id) => http.delete(`/resumes/${id}`),
}
