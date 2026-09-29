import http from './http'

export const authApi = {
  login: (phone, password) => http.post('/auth/login', { phone, password }),
  register: (payload) => http.post('/auth/register', payload),
  me: () => http.get('/auth/me'),
  forgotCode: (phone) => http.post('/auth/forgot-code', { phone }),
  resetPassword: (payload) => http.post('/auth/reset-password', payload),
  getQuota: () => http.get('/auth/quota'),
  rechargePackages: () => http.get('/auth/recharge-packages'),
  recharge: (packageId) => http.post('/auth/recharge', { package_id: packageId }),
}
