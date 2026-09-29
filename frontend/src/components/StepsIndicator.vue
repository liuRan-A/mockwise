<template>
  <div class="card mw-card" style="padding: 14px 0; margin-bottom: 20px;">
    <div class="steps">
      <div
        v-for="(s, i) in steps"
        :key="s.key"
        style="display:flex; align-items:center; gap:8px;"
      >
        <div class="step" :class="stateOf(i)">
          <span class="dot">
            <span v-if="stateOf(i) === 'done'">✓</span>
            <span v-else>{{ i + 1 }}</span>
          </span>
          <span class="label">{{ s.label }}</span>
        </div>
        <span v-if="i < steps.length - 1" class="connector" :class="{ done: stateOf(i) === 'done' }"></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  current: { type: Number, default: 1 }, // 1..4
})

const steps = [
  { key: 'form', label: '选择面试形式' },
  { key: 'set', label: '选择套题' },
  { key: 'answer', label: '全真模拟作答' },
  { key: 'report', label: '综合评分报告' },
]

function stateOf(i) {
  const idx = i + 1
  if (idx < props.current) return 'done'
  if (idx === props.current) return 'current'
  return ''
}
</script>
