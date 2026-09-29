<template>
  <div class="score-ring" :style="ringStyle">
    <span class="score-num" :style="{ color: '#3E63DD' }">{{ displayScore }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  score: { type: Number, default: 0 },
  size: { type: Number, default: 180 },
})
const pct = computed(() => Math.max(0, Math.min(100, props.score)))
const displayScore = computed(() => Math.round(props.score))
const ringStyle = computed(() => {
  const outer = props.size
  const inner = outer - 36
  return {
    width: `${outer}px`, height: `${outer}px`,
    background: `conic-gradient(var(--primary) 0 ${pct.value}%, var(--border-soft) ${pct.value}% 100%)`,
    '--inner': `${inner}px`,
  }
})
</script>

<style scoped>
.score-ring {
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  position: relative;
}
.score-ring::after {
  content: ''; width: var(--inner); height: var(--inner); border-radius: 50%;
  background: var(--card); position: absolute;
}
.score-num { position: relative; font-size: 56px; font-weight: 700; }
</style>
