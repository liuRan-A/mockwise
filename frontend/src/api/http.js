import axios from 'axios'
import { message } from 'ant-design-vue'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截：附带 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('mockwise_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一拆 {code,msg,data}
http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      message.error(body.msg || '请求失败')
      return Promise.reject(new Error(body.msg || '请求失败'))
    }
    return body
  },
  (err) => {
    const status = err.response?.status
    const msg = err.response?.data?.detail || err.response?.data?.msg || err.message
    if (status === 401) {
      localStorage.removeItem('mockwise_token')
      localStorage.removeItem('mockwise_user')
      if (location.pathname !== '/login') {
        message.error('登录已过期，请重新登录')
        location.href = '/login'
      }
    } else {
      message.error(msg || '网络异常')
    }
    return Promise.reject(err)
  }
)

export default http
