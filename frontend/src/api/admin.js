import http from './http'

export const adminApi = {
  stats: () => http.get('/admin/stats'),
  users: (params) => http.get('/admin/users', { params }),
  userDetail: (userId) => http.get(`/admin/users/${userId}`),
  setUserStatus: (userId, status) =>
    http.patch(`/admin/users/${userId}/status`, null, { params: { status } }),
  sessions: (params) => http.get('/admin/sessions', { params }),
  resumes: (params) => http.get('/admin/resumes', { params }),
  resumeDetail: (resumeId) => http.get(`/admin/resumes/${resumeId}`),
  // —— 面试回放（管理后台专用） ——
  records: (params) => http.get('/admin/records', { params }),
  sessionDetail: (sessionId) => http.get(`/admin/sessions/${sessionId}/detail`),
  // 导出 CSV（返回 blob，前端触发下载）
  exportUsers: () => http.get('/admin/users/export', { responseType: 'blob' }),
  exportSessions: (params) => http.get('/admin/sessions/export', { params, responseType: 'blob' }),
  exportRecords: (params) => http.get('/admin/records/export', { params, responseType: 'blob' }),
  exportResumes: (params) => http.get('/admin/resumes/export', { params, responseType: 'blob' }),
}

// —— 内容配置后台（套题 / 题目 / 群面虚拟候选人人设）——
export const contentApi = {
  // 套题
  sets: () => http.get('/admin/content/sets'),
  setDetail: (id) => http.get(`/admin/content/sets/${id}`),
  createSet: (data) => http.post('/admin/content/sets', data),
  updateSet: (id, data) => http.put(`/admin/content/sets/${id}`, data),
  deleteSet: (id) => http.delete(`/admin/content/sets/${id}`),
  togglePublish: (id, published) =>
    http.post(`/admin/content/sets/${id}/publish`, null, { params: { published } }),
  // 题目
  questions: (setId) => http.get(`/admin/content/sets/${setId}/questions`),
  createQuestion: (setId, data) => http.post(`/admin/content/sets/${setId}/questions`, data),
  updateQuestion: (qid, data) => http.put(`/admin/content/questions/${qid}`, data),
  deleteQuestion: (qid) => http.delete(`/admin/content/questions/${qid}`),
  aiRefAnswer: (qid) => http.post(`/admin/content/questions/${qid}/ai-ref-answer`),
  // 群面虚拟候选人人设
  personas: () => http.get('/admin/content/personas'),
  createPersona: (data) => http.post('/admin/content/personas', data),
  updatePersona: (id, data) => http.put(`/admin/content/personas/${id}`, data),
  deletePersona: (id) => http.delete(`/admin/content/personas/${id}`),
  // 高危操作：force=1 由持审批权者直执行，跳过人工卡点
  deleteSetForce: (id) => http.delete(`/admin/content/sets/${id}`, { params: { force: 1 } }),
  deleteQuestionForce: (qid) =>
    http.delete(`/admin/content/questions/${qid}`, { params: { force: 1 } }),
  deletePersonaForce: (id) =>
    http.delete(`/admin/content/personas/${id}`, { params: { force: 1 } }),
  togglePublishForce: (id, published) =>
    http.post(`/admin/content/sets/${id}/publish`, null, { params: { published, force: 1 } }),
}

// —— 人工审批卡点（高危变更 草稿 → 待审 → 复核）——
export const approvalApi = {
  list: (status, limit) =>
    http.get('/admin/approvals', { params: { status, limit } }),
  pendingCount: () => http.get('/admin/approvals/pending-count'),
  detail: (id) => http.get(`/admin/approvals/${id}`),
  approve: (id, comment) => http.post(`/admin/approvals/${id}/approve`, { comment }),
  reject: (id, comment) => http.post(`/admin/approvals/${id}/reject`, { comment }),
  cancel: (id) => http.post(`/admin/approvals/${id}/cancel`),
}

// —— 可观测性（成功率 / 耗时 / Token 成本 / 上下文命中 / 量化评测）——
export const observabilityApi = {
  llmMetrics: (hours, scene) =>
    http.get('/admin/observability/metrics/llm', { params: { hours, scene } }),
  contextMetrics: (hours) =>
    http.get('/admin/observability/metrics/context', { params: { hours } }),
  calls: (limit, scene) =>
    http.get('/admin/observability/calls', { params: { limit, scene } }),
  trace: (traceId) => http.get(`/admin/observability/traces/${traceId}`),
  runEval: (repeat, offline) =>
    http.post('/admin/observability/eval/run', null, { params: { repeat, offline } }),
  latestEval: () => http.get('/admin/observability/eval/latest'),
  evalRuns: (limit) => http.get('/admin/observability/eval/runs', { params: { limit } }),
}

// —— CMS 运营内容管理：公告 / 分类标签 / 轮播广告（管理员）——
export const cmsApi = {
  // 公告
  announcements: (params) => http.get('/admin/cms/announcements', { params }),
  createAnnouncement: (data) => http.post('/admin/cms/announcements', data),
  updateAnnouncement: (id, data) => http.put(`/admin/cms/announcements/${id}`, data),
  deleteAnnouncement: (id) => http.delete(`/admin/cms/announcements/${id}`),
  // 分类标签
  categories: (kind) => http.get('/admin/cms/categories', { params: { kind } }),
  createCategory: (data) => http.post('/admin/cms/categories', data),
  updateCategory: (id, data) => http.put(`/admin/cms/categories/${id}`, data),
  deleteCategory: (id) => http.delete(`/admin/cms/categories/${id}`),
  // 轮播广告
  carousels: (params) => http.get('/admin/cms/carousels', { params }),
  createCarousel: (data) => http.post('/admin/cms/carousels', data),
  updateCarousel: (id, data) => http.put(`/admin/cms/carousels/${id}`, data),
  deleteCarousel: (id) => http.delete(`/admin/cms/carousels/${id}`),
}

// —— 用户管理：创建 / 编辑 / 删除（管理员）——
export const userApi = {
  create: (data) => http.post('/admin/users', data),
  update: (id, data) => http.put(`/admin/users/${id}`, data),
  remove: (id) => http.delete(`/admin/users/${id}`),
}
