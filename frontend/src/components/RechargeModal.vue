<template>
  <a-modal :open="open" @update:open="(v) => emit('update:open', v)" title="充值次数" :footer="null">
    <p class="quota-line" :class="{ muted: !store.quota }">
      <template v-if="store.quota">
        当前剩余：<b>{{ store.quota.simulated_left }}</b> / {{ store.quota.simulated_total }} 次
      </template>
      <template v-else>登录后可查看与充值你的模拟次数</template>
    </p>
    <div class="pkg-list">
      <div class="pkg" v-for="p in packages" :key="p.id">
        <div class="pkg-info">
          <div class="pkg-name">{{ p.name }}</div>
          <div class="pkg-amount">+{{ p.amount }} 次</div>
        </div>
        <div class="pkg-right">
          <div class="pkg-price">¥{{ p.price }}</div>
          <a-button
            type="primary"
            size="small"
            :loading="loadingId === p.id"
            :disabled="!store.isLoggedIn"
            @click="buy(p)"
          >充值</a-button>
        </div>
      </div>
    </div>
    <p class="demo-note">demo：确认即到账，无真实支付</p>
  </a-modal>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { authApi } from '@/api'
import { useUserStore } from '@/store/user'

defineProps({ open: Boolean })
const emit = defineEmits(['update:open', 'recharged'])
const store = useUserStore()
const packages = ref([])
const loadingId = ref('')

onMounted(async () => {
  try {
    packages.value = await authApi.rechargePackages()
  } catch (e) { /* 静默 */ }
})

async function buy(p) {
  if (!store.isLoggedIn) {
    message.warning('请先登录后再充值')
    return
  }
  loadingId.value = p.id
  try {
    await store.recharge(p.id)
    message.success(`成功充值 ${p.amount} 次`)
    emit('recharged')
  } catch (e) { /* 拦截器已提示 */ } finally {
    loadingId.value = ''
  }
}
</script>

<style scoped>
.quota-line { margin: 0 0 12px; font-size: 14px; }
.quota-line.muted { color: #999; }
.quota-line b { color: var(--primary); }
.pkg-list { display: flex; flex-direction: column; gap: 10px; }
.pkg {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border: 1px solid #eee; border-radius: 10px;
}
.pkg-info { display: flex; flex-direction: column; gap: 2px; }
.pkg-name { font-weight: 700; }
.pkg-amount { color: var(--primary); font-weight: 600; font-size: 13px; }
.pkg-right { display: flex; align-items: center; gap: 12px; }
.pkg-price { color: #FF9A23; font-weight: 700; }
.demo-note { color: #999; font-size: 12px; margin: 14px 0 0; }
</style>
