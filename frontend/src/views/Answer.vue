<template>
  <div class="container">
    <StepsIndicator :current="3" />
    <a-spin :spinning="loading">
      <GroupAnswer
        v-if="mode === 'group'"
        :session="session"
        :session-id="sessionId"
        :questions="questions"
        :loading="loading"
      />
      <SemiAnswer
        v-else-if="mode === 'semi'"
        :session="session"
        :session-id="sessionId"
        :questions="questions"
        :loading="loading"
      />
      <StructuredAnswer
        v-else
        :session="session"
        :session-id="sessionId"
        :questions="questions"
        :loading="loading"
      />
    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import StepsIndicator from '@/components/StepsIndicator.vue'
import GroupAnswer from '@/components/GroupAnswer.vue'
import SemiAnswer from '@/components/SemiAnswer.vue'
import StructuredAnswer from '@/components/StructuredAnswer.vue'
import { useFlowStore } from '@/store/flow'
import { sessionApi } from '@/api'

const route = useRoute()
const router = useRouter()
const flow = useFlowStore()

const loading = ref(false)
const sessionId = ref(route.params.sessionId ? Number(route.params.sessionId) : null)
const session = ref(null)
const questions = ref([])

// 按面试形式分发：group=辩论室 / semi=半结构化对话流 / structured=结构化视频面试对话流
const mode = computed(() => session.value?.form_type || flow.formType || 'structured')

async function init() {
  if (!flow.selectedSet) {
    message.warning('请先选择套题')
    router.push('/set'); return
  }
  loading.value = true
  try {
    const res = await sessionApi.create({
      set_id: flow.selectedSet.id, form_type: flow.formType,
      voice_mode: flow.voiceMode, difficulty: flow.difficulty,
      enable_followup: flow.enableFollowup, peer_count: flow.peerCount,
      // 只要用户已上传简历，无论结构化/半结构化，都会按简历画像动态出题
      // 没简历时后端会安全降级为纯题库题，传 true 不影响行为
      use_resume: true,
    })
    sessionId.value = res.session_id; flow.setSession(res.session_id)
    const detail = await sessionApi.get(res.session_id)
    session.value = detail; questions.value = detail.questions || []
  } catch (e) { router.push('/set') }
  finally { loading.value = false }
}

onMounted(() => {
  if (route.params.sessionId) {
    loading.value = true
    sessionApi.get(Number(route.params.sessionId)).then((d) => {
      session.value = d || {}
      sessionId.value = d?.id
      questions.value = d?.questions || []
    }).catch(() => { router.push('/set') })
      .finally(() => { loading.value = false })
  } else {
    init()
  }
})
</script>
