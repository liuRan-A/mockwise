import { defineStore } from 'pinia'

/**
 * 模拟流程上下文 store：保存选中的面试形式、套题、当前场次
 * 让 Dashboard → SelectForm → SelectSet → Answer → Report 之间无后端依赖地串联
 */
export const useFlowStore = defineStore('flow', {
  state: () => ({
    formType: 'structured',      // structured / group / semi
    voiceMode: 'voice',          // text / voice / mixed
    difficulty: 'medium',
    enableFollowup: true,
    peerCount: 0,
    selectedSet: null,           // QuestionSetOut
    sessionId: null,             // 当前场次 id
    reportId: null,              // 当前报告 id
  }),
  actions: {
    setForm(formType, opts = {}) {
      this.formType = formType
      Object.assign(this, opts)
    },
    setSet(set) {
      this.selectedSet = set
    },
    setSession(id) {
      this.sessionId = id
    },
    setReport(id) {
      this.reportId = id
    },
    reset() {
      this.sessionId = null
      this.reportId = null
    },
  },
})
