<template>
  <div class="shell">
    <header class="appbar">
      <div class="brand" @click="$router.push('/dashboard')">
        <div class="brand-mark">M</div>
        <span class="brand-name">Mockwise · 模拟面试助手</span>
      </div>
      <div class="userbox">
        <span v-if="quotaText" class="mw-chip success">{{ quotaText }}</span>
        <a-button class="recharge-btn" size="small" @click="rechargeOpen = true">
          <span class="coin">◆</span> 充值
        </a-button>
        <a-dropdown>
          <div class="avatar" style="cursor:pointer">{{ store.avatarInitial }}</div>
          <template #overlay>
            <a-menu>
              <a-menu-item disabled>{{ store.nickname }}</a-menu-item>
              <a-menu-divider />
              <a-menu-item @click="$router.push('/history')">练习历史</a-menu-item>
              <a-menu-item @click="logout">退出登录</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </header>

    <div class="body">
      <aside class="sidenav">
        <button
          v-for="item in navItems"
          :key="item.name"
          class="nav-item"
          :class="{ active: activeNav === item.name }"
          @click="go(item.path)"
        >
          <svg class="nav-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <template v-if="item.name === 'dashboard'">
              <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
              <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
              <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
              <rect x="9" y="9" width="5.5" height="5.5" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            </template>
            <template v-else-if="item.name === 'form'">
              <rect x="5.5" y="1.5" width="5" height="8" rx="2.5" stroke="currentColor" stroke-width="1.4"/>
              <path d="M2.5 7.5a5.5 5.5 0 0 0 11 0M8 13v1.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </template>
            <template v-else-if="item.name === 'special'">
              <circle cx="8" cy="8" r="6.2" stroke="currentColor" stroke-width="1.4"/>
              <circle cx="8" cy="8" r="2.4" stroke="currentColor" stroke-width="1.4"/>
            </template>
            <template v-else>
              <circle cx="8" cy="8" r="6.2" stroke="currentColor" stroke-width="1.4"/>
              <path d="M8 4.5V8l2.4 1.6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </template>
          </svg>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </aside>

      <main class="page">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <RechargeModal v-model:open="rechargeOpen" @recharged="onRecharged" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import RechargeModal from '@/components/RechargeModal.vue'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const navItems = computed(() => {
  const items = [
    { name: 'dashboard', label: '工作台', path: '/dashboard' },
    { name: 'form', label: '模拟面试', path: '/form' },
    { name: 'special', label: '专项练习', path: '/special' },
    { name: 'resume', label: '我的简历', path: '/resume' },
    { name: 'history', label: '练习历史', path: '/history' },
  ]
  if (store.user?.role === 'admin') {
    items.push({ name: 'admin', label: '管理后台', path: '/admin' })
  }
  return items
})

// 模拟面试流程内的页面（选套题/作答/报告/逐题回放）都归到「模拟面试」高亮
const flowNames = new Set(['form', 'set', 'answer', 'answerById', 'report', 'reportById', 'questionDetail'])

const activeNav = computed(() => {
  const name = route.name?.split('ById')[0] || route.name
  if (flowNames.has(String(name))) return 'form'
  return navItems.value.find(i => i.name === name)?.name || 'dashboard'
})

const rechargeOpen = ref(false)

const quotaText = computed(() => {
  if (!store.isLoggedIn || !store.quota) return ''
  return `本月剩余 ${store.quota.simulated_left}/${store.quota.simulated_total} 次`
})

function go(path) {
  router.push(path)
}

async function loadQuota() {
  if (store.isLoggedIn) await store.fetchQuota().catch(() => {})
}
onMounted(loadQuota)
watch(() => route.fullPath, loadQuota)

function onRecharged() {
  store.fetchQuota().catch(() => {})
}

function logout() {
  store.logout()
  router.push('/login')
}
</script>

<style scoped>
.shell { min-height: 100vh; display: flex; flex-direction: column; }
.appbar {
  position: sticky; top: 0; z-index: 50;
  height: 64px; background: var(--card);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px;
}
.brand { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.brand-mark {
  width: 32px; height: 32px; border-radius: 9px; background: var(--primary);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 17px;
}
.brand-name { font-weight: 700; font-size: 16px; }
.userbox { display: flex; align-items: center; gap: 12px; }
.recharge-btn { border-color: var(--primary); color: var(--primary); }
.recharge-btn .coin { font-size: 11px; margin-right: 3px; }
.avatar {
  width: 36px; height: 36px; border-radius: 50%; background: var(--primary);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700;
}

.body { flex: 1; display: flex; min-height: 0; }
.sidenav {
  width: 208px; flex-shrink: 0;
  padding: 16px 12px;
  border-right: 1px solid var(--border);
  background: var(--card);
  display: flex; flex-direction: column; gap: 4px;
  position: sticky; top: 64px;
  height: calc(100vh - 64px);
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 14px; border: none; border-radius: 10px;
  background: transparent; color: var(--text-2);
  font-size: 14px; font-weight: 500; text-align: left;
  transition: all .15s;
}
.nav-item:hover:not(.active) { background: var(--bg); color: var(--text-1); }
.nav-item.active { background: var(--primary-soft); color: var(--primary); font-weight: 700; }
.nav-icon { flex-shrink: 0; }

.page { flex: 1; min-width: 0; }

.fade-enter-active, .fade-leave-active { transition: opacity .18s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 900px) {
  .sidenav { width: 64px; padding: 16px 8px; }
  .nav-item { justify-content: center; padding: 11px; }
  .nav-label { display: none; }
}
</style>
