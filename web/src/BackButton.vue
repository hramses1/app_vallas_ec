<script setup>
import Icon from './Icon.vue'

defineEmits(['click'])
</script>

<template>
  <div class="back-bar">
    <button class="back-button" type="button" @click="$emit('click')">
      <Icon name="back" />
      Volver a la lista
    </button>
  </div>
</template>

<style scoped>
/* Fija arriba para no tener que subir en una ficha larga */
.back-bar {
  position: sticky;
  top: 0;
  z-index: 2;
  margin: 0 -16px;
  padding: 8px 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.back-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  padding: 8px 14px 8px 8px;
  background: var(--surface-soft);
  border: 0;
  border-radius: var(--radius-control);
  font-size: 15px;
  font-weight: 600;
  transition: background-color 150ms ease, transform 160ms var(--ease-out);
}
.back-button:hover { background: var(--line); }
.back-button:active { transform: scale(0.97); }
</style>
