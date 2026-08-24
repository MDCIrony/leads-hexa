<script setup lang="ts">
defineProps<{ bloque?: string; idea?: string }>()
</script>

<template>
  <div class="slidev-layout blocked">
    <header class="blocked-head">
      <span class="blocked-tag">{{ bloque }}</span>
      <span class="blocked-num">{{ $slidev.nav.currentPage }} / {{ $slidev.nav.total }}</span>
    </header>
    <main class="blocked-body">
      <slot />
    </main>
    <footer v-if="idea" class="blocked-foot">{{ idea }}</footer>
  </div>
</template>
