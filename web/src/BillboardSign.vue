<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import Icon from './Icon.vue'

// Dibuja la valla a escala real junto a una persona de 1,70 m, con un anuncio de ejemplo
const props = defineProps({
  width: { type: Number, required: true },
  height: { type: Number, required: true },
  type: { type: String, default: 'estatica' },
})

const PERSON_M = 1.7
const VIEW_W = 300
const GROUND = 158
// Altura bajo la valla: en un puente es el paso de los carros. Es ilustrativa, no una medida real.
const clearance = computed(() => (props.type === 'puente' ? 3.2 : 2.5))
const EXAMPLES = ['apertura', 'comida', 'hogar']

const example = ref(0)
const ownImage = ref(null)

const scale = computed(() => Math.min(230 / props.width, 120 / (props.height + clearance.value)))
const panel = computed(() => {
  const w = props.width * scale.value
  const h = props.height * scale.value
  const post = clearance.value * scale.value
  return { x: 54 + (230 - w) / 2, y: GROUND - post - h, w, h, post }
})
const person = computed(() => PERSON_M * scale.value)
const metres = (value) => `${String(value).replace('.', ',')} m`
const ratio = computed(() => String(Math.round((props.width / props.height) * 10) / 10).replace('.', ','))
const adColor = computed(() => ({ apertura: '#f5b700', comida: '#b3261e', hogar: '#12355b' })[EXAMPLES[example.value]])

function change(step) {
  ownImage.value = null
  example.value = (example.value + step + EXAMPLES.length) % EXAMPLES.length
}

// La imagen se queda en el navegador: no se envía a ningún servidor
function chooseImage(event) {
  const [file] = event.target.files
  if (!file) return
  if (ownImage.value) URL.revokeObjectURL(ownImage.value)
  ownImage.value = URL.createObjectURL(file)
}

onBeforeUnmount(() => {
  if (ownImage.value) URL.revokeObjectURL(ownImage.value)
})
</script>

<template>
  <figure class="sign">
    <svg
      :viewBox="`0 ${panel.y - 22} ${VIEW_W} ${GROUND + 8 - (panel.y - 22)}`"
      role="img"
      :aria-label="`Valla de ${metres(width)} de ancho por ${metres(height)} de alto con un anuncio de ejemplo, junto a una persona como referencia`"
    >
      <rect x="0" :y="panel.y - 22" :width="VIEW_W" :height="GROUND - panel.y + 22" class="sky" />
      <rect x="0" :y="GROUND" :width="VIEW_W" height="8" class="road" />
      <line x1="0" :y1="GROUND + 4" :x2="VIEW_W" :y2="GROUND + 4" class="lane" />

      <!-- Estructura: puente peatonal con pilares, o poste de valla -->
      <template v-if="type === 'puente'">
        <rect x="0" :y="panel.y + panel.h - 3" :width="VIEW_W" height="7" class="post" />
        <rect :x="panel.x - 8" :y="panel.y + panel.h" width="7" :height="panel.post" class="post" />
        <rect :x="panel.x + panel.w + 1" :y="panel.y + panel.h" width="7" :height="panel.post" class="post" />
      </template>
      <rect v-else :x="panel.x + panel.w / 2 - 3" :y="panel.y + panel.h" width="6" :height="panel.post" class="post" />

      <!-- Anuncio -->
      <rect :x="panel.x" :y="panel.y" :width="panel.w" :height="panel.h" :fill="ownImage ? '#fff' : adColor" />
      <image
        v-if="ownImage"
        :href="ownImage"
        :x="panel.x"
        :y="panel.y"
        :width="panel.w"
        :height="panel.h"
        preserveAspectRatio="xMidYMid slice"
      />
      <svg v-else :x="panel.x" :y="panel.y" :width="panel.w" :height="panel.h" viewBox="0 0 250 100">
        <g v-if="EXAMPLES[example] === 'apertura'" class="ad">
          <text x="125" y="46" text-anchor="middle" font-size="27" font-weight="800" fill="#23282d">GRAN APERTURA</text>
          <rect x="52" y="60" width="146" height="26" rx="13" fill="#23282d" />
          <text x="125" y="79" text-anchor="middle" font-size="17" font-weight="600" fill="#f5b700">Tu negocio, aquí</text>
        </g>
        <g v-else-if="EXAMPLES[example] === 'comida'" class="ad">
          <circle cx="50" cy="50" r="36" fill="#f5b700" />
          <circle cx="50" cy="50" r="24" fill="#fff4cc" />
          <text x="94" y="46" font-size="20" font-weight="800" fill="#fff">Tu restaurante</text>
          <text x="94" y="68" font-size="14" font-weight="400" fill="#fff">a 5 minutos de aquí</text>
        </g>
        <g v-else class="ad">
          <path d="M18 88V52h16V34h18v22h14V42h16v46z" fill="#6f9bc8" />
          <text x="100" y="46" font-size="24" font-weight="800" fill="#fff">Tu próximo</text>
          <text x="100" y="74" font-size="24" font-weight="800" fill="#f5b700">hogar</text>
        </g>
      </svg>
      <rect :x="panel.x" :y="panel.y" :width="panel.w" :height="panel.h" class="frame" />

      <text :x="panel.x + panel.w / 2" :y="panel.y - 7" text-anchor="middle" class="measure">{{ metres(width) }}</text>
      <text :x="Math.min(panel.x + panel.w + 6, VIEW_W - 28)" :y="panel.y + panel.h / 2 + 4" class="measure measure--side">{{ metres(height) }}</text>

      <g class="person">
        <circle cx="26" :cy="GROUND - person + person * 0.1" :r="person * 0.1" />
        <rect
          :x="26 - person * 0.09"
          :y="GROUND - person + person * 0.21"
          :width="person * 0.18"
          :height="person * 0.79"
          :rx="person * 0.06"
        />
      </g>
    </svg>

    <figcaption>
      <div class="controls">
        <button type="button" aria-label="Ver el ejemplo anterior" @click="change(-1)">
          <Icon name="back" />
        </button>
        <span role="status">{{ ownImage ? 'Tu imagen' : `Ejemplo ${example + 1} de ${EXAMPLES.length}` }}</span>
        <button type="button" aria-label="Ver el siguiente ejemplo" @click="change(1)">
          <Icon name="back" class="flip" />
        </button>
        <label class="upload">
          Probar con mi imagen
          <input type="file" accept="image/*" @change="chooseImage" />
        </label>
      </div>
      <p>
        Anuncio de ejemplo a la escala real de la valla. Para tu diseño, usa una imagen {{ ratio }} veces más ancha que alta.
        <template v-if="ownImage">Tu imagen no se envía: solo se ve en este navegador.</template>
      </p>
    </figcaption>
  </figure>
</template>

<style scoped>
.sign { display: grid; gap: 6px; margin: 2px 0; }
.sign > svg { display: block; width: 100%; height: auto; border-radius: var(--radius-panel); }
.sky { fill: #dcebf5; }
.road { fill: #4a5158; }
.lane { stroke: #f5b700; stroke-width: 1.2; stroke-dasharray: 10 8; }
.post { fill: var(--asphalt); }
.frame { fill: none; stroke: var(--asphalt); stroke-width: 2; }
.ad text { font-family: Overpass, 'Segoe UI', sans-serif; }
.measure { fill: var(--asphalt); font-size: 12px; font-weight: 600; }
.person { fill: var(--asphalt); }

.controls { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 13px; }
.controls button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  background: var(--surface-soft);
  border: 0;
  border-radius: var(--radius-control);
  transition: background-color 150ms ease, transform 160ms var(--ease-out);
}
.controls button:hover { background: var(--line); }
.controls button:active { transform: scale(0.94); }
.flip { transform: scaleX(-1); }
.upload {
  margin-left: auto;
  padding: 8px 12px;
  background: var(--surface-soft);
  border-radius: var(--radius-control);
  font-weight: 600;
  cursor: pointer;
  transition: background-color 150ms ease;
}
.upload:hover { background: var(--line); }
.upload:focus-within { outline: 3px solid var(--lane-yellow); outline-offset: 2px; }
.upload input { position: absolute; width: 1px; height: 1px; opacity: 0; }
figcaption p { margin-top: 5px; color: var(--muted); font-size: 12.5px; }
</style>
