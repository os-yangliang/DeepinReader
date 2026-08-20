<template>
  <header class="ptb">
    <div class="ptb-left">
      <div class="ptb-icon" :style="{ color: accent, background: `${accent}1a` }">
        <component :is="icon" :size="18" />
      </div>
      <div class="ptb-titles">
        <h1 class="ptb-title">{{ title }}</h1>
        <p v-if="subtitle" class="ptb-subtitle">{{ subtitle }}</p>
      </div>

      <div v-if="docName" class="ptb-doc">
        <FileText :size="13" />
        <span class="truncate">{{ docName }}</span>
        <span v-if="docReady" class="ptb-ready">
          <Check :size="11" /> 就绪
        </span>
      </div>
    </div>

    <div class="ptb-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { FileText, Check } from 'lucide-vue-next'
import { store } from '../store'

const props = defineProps({
  icon: { type: [Object, Function], required: true },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  accent: { type: String, default: 'var(--accent-1)' },
})

const docName = computed(() => store.documentInfo?.filename || '')
const docReady = computed(() => !!store.documentInfo?.document_id)
</script>

<style scoped>
.ptb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0 1.5rem;
  height: 56px;
  flex-shrink: 0;
  background: var(--bg-glass);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-default);
}
.ptb-left {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
}
.ptb-icon {
  width: 32px;
  height: 32px;
  border-radius: 0.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ptb-titles {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  min-width: 0;
}
.ptb-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-heading);
  white-space: nowrap;
}
.ptb-subtitle {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ptb-doc {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.7rem;
  margin-left: 0.5rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  max-width: 280px;
}
.ptb-doc svg {
  flex-shrink: 0;
  color: var(--text-muted);
}
.ptb-ready {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  color: var(--positive);
  font-size: 0.7rem;
  white-space: nowrap;
}
.ptb-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
</style>