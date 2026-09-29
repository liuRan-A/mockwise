import { defineStore } from 'pinia'
import { authApi } from '@/api'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('mockwise_token') || '',
    user: JSON.parse(localStorage.getItem('mockwise_user') || 'null'),
    quota: JSON.parse(localStorage.getItem('mockwise_quota') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    nickname: (s) => s.user?.nickname || '游客',
    avatarInitial: (s) => (s.user?.nickname || 'U').charAt(0),
  },
  actions: {
    async login(phone, password) {
      const data = await authApi.login(phone, password)
      this._setAuth(data)
      return data
    },
    async register(payload) {
      const data = await authApi.register(payload)
      this._setAuth(data)
      return data
    },
    async fetchMe() {
      const u = await authApi.me()
      this.user = u
      localStorage.setItem('mockwise_user', JSON.stringify(u))
      return u
    },
    async forgotCode(phone) {
      return authApi.forgotCode(phone)
    },
    async resetPassword(payload) {
      return authApi.resetPassword(payload)
    },
    async fetchQuota() {
      const q = await authApi.getQuota()
      this.quota = q
      localStorage.setItem('mockwise_quota', JSON.stringify(q))
      return q
    },
    async recharge(packageId) {
      const q = await authApi.recharge(packageId)
      this.quota = q
      localStorage.setItem('mockwise_quota', JSON.stringify(q))
      return q
    },
    logout() {
      this.token = ''
      this.user = null
      this.quota = null
      localStorage.removeItem('mockwise_token')
      localStorage.removeItem('mockwise_user')
      localStorage.removeItem('mockwise_quota')
    },
    _setAuth(data) {
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('mockwise_token', data.access_token)
      localStorage.setItem('mockwise_user', JSON.stringify(data.user))
      // 登录后顺带拉取配额
      this.fetchQuota().catch(() => {})
    },
  },
})
