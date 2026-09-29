<template>
  <a-config-provider :theme="themeConfig">
    <router-view />
  </a-config-provider>
</template>

<script setup>
import { theme } from 'ant-design-vue'

const themeConfig = {
  token: {
    colorPrimary: '#3E63DD',
    colorSuccess: '#2FA36B',
    colorWarning: '#E8912D',
    colorError: '#D8504F',
    colorInfo: '#3E63DD',
    borderRadius: 10,
    fontFamily: '"Sarasa Gothic SC", "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
  },
  algorithm: theme.defaultAlgorithm,
}
</script>
