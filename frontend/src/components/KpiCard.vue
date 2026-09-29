<template>
  <div class="kpi" :class="accent">
    <span class="label">{{ label }}</span>
    <span class="value">{{ value }}<small v-if="unit" style="font-size:14px; color:var(--text-3); margin-left:4px;">{{ unit }}</small></span>
    <span v-if="delta" class="delta" :class="deltaClass">
      <span v-if="deltaType === 'up'">↑</span>
      <span v-else-if="deltaType === 'down'">↓</span>
      {{ delta }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  label: String, value: [String, Number], unit: String,
  delta: String, deltaType: { type: String, default: 'up' }, // up / down / muted
  accent: { type: String, default: '' }, // 可选 'primary'
})

const deltaClass = computed(() => {
  if (props.deltaType === 'muted') return 'muted'
  return props.deltaType // up / down
})
</script>

<style scoped>
.kpi {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--r-card);
  padding: 18px 20px; display: flex; flex-direction: column; gap: 6px;
}
.kpi.primary { background: linear-gradient(135deg, var(--primary) 0%, #5B7FE8 100%); color: #fff; border: none; }
.kpi.primary .label { color: rgba(255,255,255,.85); }
.kpi.primary .value { color: #fff; }
.kpi.primary .delta { color: rgba(255,255,255,.9); }
.kpi .label { font-size: 12px; color: var(--text-3); }
.kpi .value { font-size: 28px; font-weight: 700; line-height: 1.1; }
.kpi .delta { font-size: 12px; font-weight: 600; }
.kpi .delta.up { color: var(--success); }
.kpi .delta.down { color: var(--warning); }
.kpi .delta.muted { color: var(--text-3); font-weight: 400; }
</style>
