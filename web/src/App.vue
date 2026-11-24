<script setup lang="ts">
import { RouterView } from 'vue-router'
import ToastHost from '@/components/ui/ToastHost.vue'
import ConfirmHost from '@/components/ui/ConfirmHost.vue'
import DesktopLifecycle from '@/components/common/DesktopLifecycle.vue'
</script>

<template>
  <RouterView />
  <ToastHost />
  <ConfirmHost />
  <DesktopLifecycle />
</template>
