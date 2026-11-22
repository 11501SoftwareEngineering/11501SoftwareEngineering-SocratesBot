<script setup lang="ts">
import StatusPage from '@/components/common/StatusPage.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <StatusPage :title="t('status.notFoundTitle')" :description="t('status.notFoundDescription')" />
</template>
