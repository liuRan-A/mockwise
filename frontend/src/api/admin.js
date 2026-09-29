import http from './http'

export const adminApi = {
  stats: () => http.get('/admin/stats'),
  users: (params) => http.get('/admin/users', { params }),
  setUserStatus: (userId, status) =>
    http.patch(`/admin/users/${userId}/status`, null, { params: { status } }),
  sessions: (params) => http.get('/admin/sessions', { params }),
  resumes: (params) => http.get('/admin/resumes', { params }),
  // —— 面试回放（管理后台专用） ——
  records: (params) => http.get('/admin/records', { params }),
  sessionDetail: (sessionId) => http.get(`/admin/sessions/${sessionId}/detail`),
}
