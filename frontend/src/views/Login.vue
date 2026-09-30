<template>
  <div class="login-wrap">
    <!-- 左侧品牌区 -->
    <aside class="brand-panel">
      <div class="brand-top">
        <div class="brand-mark">M</div>
        <span class="brand-name">Mockwise · 全真模拟</span>
      </div>
      <div class="brand-hero">
        <h1>AI 全真模拟面试</h1>
        <p>配置 — 模拟 — 评估 — 回放 — 改进，闭环训练你的每一次面试。</p>
      </div>
      <ul class="feature-list">
        <li>一对一 / 一对多模拟，拟真对话</li>
        <li>智能评估报告与逐题回放</li>
        <li>专属配额，随时充值加练</li>
      </ul>
    </aside>

    <!-- 右侧表单区 -->
    <main class="form-panel">
      <div class="top-actions">
        <a-button class="recharge-entry" @click="rechargeOpen = true">
          <span class="coin">◆</span> 充值次数
        </a-button>
      </div>

      <div class="form-card">
        <a-tabs v-model:activeKey="mode" class="auth-tabs">
          <a-tab-pane key="login" tab="登录" />
          <a-tab-pane key="register" tab="注册" />
        </a-tabs>

        <a-form layout="vertical" :model="form" @finish="onSubmit">
          <a-form-item label="手机号" name="phone" :rules="[{ required: true, message: '请输入手机号' }]">
            <a-input v-model:value="form.phone" placeholder="13800000000" size="large" />
          </a-form-item>
          <a-form-item label="密码" name="password" :rules="[{ required: true, message: '请输入密码' }]">
            <a-input-password v-model:value="form.password" placeholder="请输入密码" size="large" />
          </a-form-item>
          <a-form-item v-if="mode === 'register'" label="昵称（选填）" name="nickname">
            <a-input v-model:value="form.nickname" placeholder="不填则默认生成" size="large" />
          </a-form-item>

          <div class="row-between" v-if="mode === 'login'">
            <a-checkbox v-model:checked="remember">记住我</a-checkbox>
            <a class="link" @click="openForgot">忘记密码？</a>
          </div>

          <a-button v-if="mode === 'login'" type="primary" size="large" block html-type="submit" :loading="loading">
            登录
          </a-button>
          <a-button v-else type="primary" size="large" block html-type="submit" :loading="loading">
            注册并登录
          </a-button>
        </a-form>

        <p class="tip">demo 账号：13800000000 / 123456（可直接登录，或注册新号自动初始化 3 次配额）</p>
        <p class="tip admin-tip">管理后台：13800000001 / admin123（管理员角色，登录后左侧显示「管理后台」）</p>
      </div>
    </main>

    <!-- 忘记密码弹窗 -->
    <a-modal v-model:open="forgotOpen" title="重置密码" :footer="null" @cancel="resetForgot" width="420px">
      <template v-if="fpStep === 1">
        <a-form layout="vertical">
          <a-form-item label="注册手机号">
            <a-input v-model:value="fpPhone" placeholder="请输入注册手机号" size="large" />
          </a-form-item>
          <a-button type="primary" block size="large" :loading="fpLoading" @click="sendCode">获取验证码</a-button>
        </a-form>
      </template>
      <template v-else>
        <a-alert
          v-if="fpSentCode"
          type="info"
          :message="`demo 验证码：${fpSentCode}（真实场景将通过短信下发）`"
          style="margin-bottom: 14px"
        />
        <a-form layout="vertical">
          <a-form-item label="验证码">
            <a-input v-model:value="fpCode" placeholder="6 位验证码" size="large" />
          </a-form-item>
          <a-form-item label="新密码">
            <a-input-password v-model:value="fpNewPwd" placeholder="至少 6 位" size="large" />
          </a-form-item>
          <a-button type="primary" block size="large" :loading="fpLoading" @click="doReset">确认重置</a-button>
        </a-form>
      </template>
    </a-modal>

    <RechargeModal v-model:open="rechargeOpen" @recharged="onRecharged" />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useUserStore } from '@/store/user'
import RechargeModal from '@/components/RechargeModal.vue'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const mode = ref('login')
const remember = ref(true)
const form = reactive({ phone: '13800000000', password: '123456', nickname: '' })
const loading = ref(false)
const rechargeOpen = ref(false)

async function onSubmit() {
  loading.value = true
  try {
    if (mode.value === 'login') {
      await store.login(form.phone, form.password)
      message.success('登录成功')
      router.replace(route.query.redirect || '/dashboard')
    } else {
      await store.register({ phone: form.phone, password: form.password, nickname: form.nickname || '' })
      message.success('注册并登录成功')
      router.replace('/dashboard')
    }
  } catch (e) { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

function onRecharged() {
  if (!store.isLoggedIn) message.info('登录后即可使用充值的次数')
}

/* ---------------- 忘记密码流程 ---------------- */
const forgotOpen = ref(false)
const fpStep = ref(1)
const fpPhone = ref('')
const fpCode = ref('')
const fpNewPwd = ref('')
const fpSentCode = ref('')
const fpLoading = ref(false)

function openForgot() {
  forgotOpen.value = true
  fpStep.value = 1
}
function resetForgot() {
  fpStep.value = 1
  fpPhone.value = ''
  fpCode.value = ''
  fpNewPwd.value = ''
  fpSentCode.value = ''
}
async function sendCode() {
  if (!fpPhone.value) {
    message.warning('请输入手机号')
    return
  }
  fpLoading.value = true
  try {
    const d = await store.forgotCode(fpPhone.value) // demo 直接返回 {code, demo}
    fpSentCode.value = d.code
    fpStep.value = 2
    message.success('验证码已发送')
  } catch (e) { /* 拦截器已提示 */ } finally {
    fpLoading.value = false
  }
}
async function doReset() {
  if (!fpCode.value || !fpNewPwd.value) {
    message.warning('请填写验证码和新密码')
    return
  }
  if (fpNewPwd.value.length < 6) {
    message.warning('新密码至少 6 位')
    return
  }
  fpLoading.value = true
  try {
    await store.resetPassword({ phone: fpPhone.value, code: fpCode.value, new_password: fpNewPwd.value })
    message.success('密码已重置，请用新密码登录')
    forgotOpen.value = false
    resetForgot()
  } catch (e) { /* 拦截器已提示 */ } finally {
    fpLoading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh; display: flex;
  background: var(--bg);
}
.brand-panel {
  flex: 0 0 42%; max-width: 560px;
  background: linear-gradient(150deg, #3E63DD 0%, #2B3F8F 55%, #1B2030 100%);
  color: #fff; padding: 48px 56px;
  display: flex; flex-direction: column;
  position: relative; overflow: hidden;
}
.brand-top { display: flex; align-items: center; gap: 10px; }
.brand-mark {
  width: 38px; height: 38px; border-radius: 10px;
  background: rgba(255, 255, 255, .16);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 20px;
}
.brand-name { font-weight: 700; font-size: 18px; }
.brand-hero { margin-top: auto; margin-bottom: 28px; }
.brand-hero h1 { font-size: 34px; margin: 0 0 14px; line-height: 1.25; }
.brand-hero p { margin: 0; color: rgba(255, 255, 255, .78); font-size: 15px; max-width: 380px; }
.feature-list {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 14px;
}
.feature-list li {
  position: relative; padding-left: 28px;
  color: rgba(255, 255, 255, .9); font-size: 14px;
}
.feature-list li::before {
  content: "✓"; position: absolute; left: 0; top: 0;
  width: 18px; height: 18px; border-radius: 50%;
  background: rgba(255, 255, 255, .18);
  display: flex; align-items: center; justify-content: center; font-size: 11px;
}

.form-panel {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 40px; position: relative;
}
.top-actions { position: absolute; top: 28px; right: 32px; }
.recharge-entry { border-color: var(--primary); color: var(--primary); }
.recharge-entry .coin { margin-right: 4px; font-size: 12px; }

.form-card { width: 380px; max-width: 100%; }
.auth-tabs { margin-bottom: 4px; }
.row-between {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 18px;
}
.link { color: var(--primary); cursor: pointer; font-size: 13px; }
.link:hover { text-decoration: underline; }
.tip { margin-top: 18px; color: var(--text-3); font-size: 12px; }
.tip.admin-tip { color: var(--primary); margin-top: 6px; font-weight: 600; }

@media (max-width: 820px) {
  .brand-panel { display: none; }
}
</style>
