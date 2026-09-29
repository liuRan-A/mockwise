<template>
  <div class="dim-row">
    <span class="name">{{ name }}</span>
    <div class="shell">
      <div class="fill" :class="{ warning: isWarning }" :style="{ width: pct + '%' }"></div>
    </div>
    <span class="score">{{ score }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  name: String, score: { type: Number, default: 0 }, threshold: { type: Number, default: 70 },
})
const pct = computed(() => Math.max(0, Math.min(100, props.score)))
const isWarning = computed(() => props.score < props.threshold)
</script>

<style scoped>
.dim-row { display: grid; grid-template-columns: 90px 1fr 50px; gap: 10px; align-items: center; }
.dim-row .name { font-size: 13px; color: var(--text-2); }
.dim-row .shell { height: 10px; background: var(--border-soft); border-radius: 5px; overflow: hidden; }
.dim-row .fill { height: 100%; border-radius: 5px; background: var(--primary); transition: width .4s ease; }
.dim-row .fill.warning { background: var(--warning); }
.dim-row .score { font-size: 13px; font-weight: 700; text-align: right; }
</style>
