<template>
  <div class="empty">
    <div class="empty-icon" :style="{ color: accent, background: `${accent}14` }">
      <component :is="icon" :size="30" />
    </div>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: [Object, Function], required: true },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  accent: { type: String, default: 'var(--accent-1)' },
})
</script>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 3rem 1.5rem;
  height: 100%;
}
.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.1rem;
  border: 1px solid var(--border-default);
}
.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-heading);
  margin-bottom: 0.4rem;
}
.empty-desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  max-width: 380px;
  line-height: 1.6;
}
.empty-actions {
  margin-top: 1.25rem;
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: center;
}
</style>