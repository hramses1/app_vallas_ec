<script setup>
import { computed, reactive, ref } from 'vue'
import BackButton from './BackButton.vue'
import Icon from './Icon.vue'

const props = defineProps({
  point: { type: Object, default: null },
  types: { type: Object, required: true },
})
const emit = defineEmits(['close', 'locate', 'again'])

const EMPTY = {
  address: '',
  provider_name: '',
  contact_phone: '',
  price_usd: '',
  price_unit: 'mes',
  type: 'estatica',
  comment: '',
  website: '',
}
const form = reactive({ ...EMPTY })
const sending = ref(false)
const sent = ref(false)
const error = ref('')
const locating = ref(false)
const mapsInput = ref('')
const mapsStatus = ref('')
const mapsError = ref(false)
const mapsUrl = computed(() => {
  const { lat, lng } = props.point ?? { lat: -2.16, lng: -79.89 }
  return `https://www.google.com/maps/@${lat},${lng},${props.point ? 18 : 12}z`
})

const canSend = computed(() => props.point && !sending.value)
const canLocate = 'geolocation' in navigator

function useMyLocation() {
  locating.value = true
  error.value = ''
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      locating.value = false
      emit('locate', { lat: coords.latitude, lng: coords.longitude })
    },
    () => {
      locating.value = false
      error.value = 'No se pudo obtener tu ubicación. Marca el punto en el mapa.'
    },
  )
}

// Acepta coordenadas ("-2.15, -79.90") o un enlace de Google Maps, también los cortos de Compartir
async function readMapsInput() {
  const text = mapsInput.value.trim()
  mapsError.value = false
  mapsStatus.value = ''
  if (!text) return
  const coords = text.match(/^(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$/)
  if (coords) {
    emit('locate', { lat: Number(coords[1]), lng: Number(coords[2]) })
    mapsStatus.value = 'Listo: pusimos el pin en esas coordenadas.'
    return
  }
  mapsStatus.value = 'Leyendo el enlace...'
  try {
    const response = await fetch('/api/maps-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: text }),
    })
    if (!response.ok) throw new Error('sin coordenadas')
    emit('locate', await response.json())
    mapsStatus.value = 'Listo: pusimos el pin donde indica el enlace.'
  } catch {
    mapsError.value = true
    mapsStatus.value = 'Ese enlace no trae el punto. En Google Maps mantén presionado sobre la valla y copia las coordenadas que aparecen.'
  }
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    const response = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, price_usd: form.price_usd === '' ? null : form.price_usd, ...props.point }),
    })
    if (response.status === 429) {
      error.value = 'Hay demasiados reportes en este momento. Inténtalo en una hora.'
    } else if (response.status === 422) {
      error.value = 'El punto debe estar en Ecuador. Muévelo e inténtalo de nuevo.'
    } else if (!response.ok) {
      error.value = 'No se pudo enviar el reporte. Inténtalo de nuevo.'
    } else {
      sent.value = true
    }
  } catch {
    error.value = 'No se pudo enviar el reporte. Revisa tu conexión e inténtalo de nuevo.'
  }
  sending.value = false
}

function reportAnother() {
  Object.assign(form, EMPTY)
  mapsInput.value = ''
  mapsStatus.value = ''
  sent.value = false
  emit('again')
}
</script>

<template>
  <section class="report" aria-label="Reportar una valla">
    <BackButton @click="emit('close')" />

    <div v-if="sent" class="done">
      <span class="done-icon"><Icon name="check" :size="26" /></span>
      <h2>Reporte enviado</h2>
      <p>Gracias. Lo revisaremos antes de publicarlo en el mapa.</p>
      <button class="again" type="button" @click="reportAnother">Reportar otra valla</button>
    </div>

    <form v-else @submit.prevent="send">
      <h2>Reporta una valla que no está en el mapa</h2>

      <div class="step" :class="{ 'step--done': point }">
        <span class="step-icon"><Icon :name="point ? 'check' : 'target'" /></span>
        <div>
          <strong>{{ point ? 'Punto marcado' : 'Marca dónde está la valla' }}</strong>
          <p v-if="point">Puedes arrastrar el pin para ajustarlo.</p>
          <p v-else>Toca el mapa justo donde está la valla.</p>
          <button v-if="canLocate" class="link" type="button" :disabled="locating" @click="useMyLocation">
            {{ locating ? 'Buscando tu ubicación...' : 'Estoy junto a la valla: usar mi ubicación' }}
          </button>
        </div>
      </div>

      <label>
        Empresa (opcional)
        <input v-model="form.provider_name" maxlength="200" placeholder="La que aparece en la placa" />
      </label>
      <div class="price">
        <label>
          Precio en dólares (opcional)
          <input v-model="form.price_usd" type="number" min="0" step="any" inputmode="decimal" />
        </label>
        <label>
          Por
          <select v-model="form.price_unit">
            <option value="mes">mes</option>
            <option value="dia">día</option>
          </select>
        </label>
      </div>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button class="submit" type="submit" :disabled="!canSend">
        {{ sending ? 'Enviando...' : 'Enviar reporte' }}
      </button>
      <p class="muted">Solo el punto es obligatorio. Revisamos cada reporte antes de publicarlo.</p>

      <details class="more">
        <summary><Icon name="link" :size="16" /> Usar un enlace de Google Maps</summary>
        <div class="fields">
          <label>
            Pega el enlace o las coordenadas
            <input
              v-model="mapsInput"
              placeholder="https://maps.app.goo.gl/... o -2.15, -79.90"
              autocomplete="off"
              @change="readMapsInput"
              @paste="$nextTick(readMapsInput)"
            />
          </label>
          <p v-if="mapsStatus" :class="mapsError ? 'error' : 'muted'" role="status">{{ mapsStatus }}</p>
          <a :href="mapsUrl" target="_blank" rel="noopener">Abrir Google Maps</a>
        </div>
      </details>

      <details class="more">
        <summary><Icon name="plus" :size="16" /> Agregar tipo, teléfono o comentario (opcional)</summary>
        <div class="fields">
          <label>
            Tipo
            <select v-model="form.type">
              <option v-for="(label, value) in types" :key="value" :value="value">{{ label }}</option>
            </select>
          </label>
          <label>
            Teléfono que aparece en la placa
            <input v-model="form.contact_phone" maxlength="30" inputmode="tel" />
          </label>
          <label>
            Referencia o comentario
            <input v-model="form.comment" maxlength="1000" placeholder="Tamaño, si está iluminada, frente a..." />
          </label>
        </div>
      </details>

      <!-- Trampa para bots: las personas no ven este campo -->
      <input v-model="form.website" class="trap" type="text" tabindex="-1" autocomplete="off" aria-hidden="true" />
    </form>
  </section>
</template>

<style scoped>
.report { display: grid; gap: 14px; padding-bottom: 16px; }
form { display: grid; gap: 12px; }
h2 { font-size: 20px; font-weight: 800; line-height: 1.2; }
label { display: grid; gap: 4px; font-size: 13px; font-weight: 600; }
summary { display: flex; align-items: center; gap: 6px; width: fit-content; min-height: 32px; font-size: 14px; font-weight: 600; cursor: pointer; }
.fields { display: grid; gap: 10px; margin-top: 6px; }
.fields a { font-size: 14px; }
.trap { position: absolute; left: -9999px; width: 1px; height: 1px; }
.muted { color: var(--muted); font-size: 13px; }
.error { color: var(--danger); font-weight: 600; font-size: 14px; }
.link { padding: 2px 0; background: none; border: 0; color: var(--sign-green-dark); text-align: left; text-decoration: underline; text-underline-offset: 2px; }
.step { display: flex; gap: 10px; padding: 12px; background: var(--lane-yellow-soft); border-radius: var(--radius-panel); font-size: 14px; transition: background-color 200ms ease; }
.step--done { background: var(--sign-green-soft); }
.step-icon { display: grid; place-items: center; flex: none; width: 32px; height: 32px; background: var(--surface); border-radius: 50%; }
.price { display: grid; grid-template-columns: 1fr 96px; gap: 8px; align-items: end; }
.submit, .again {
  min-height: 46px;
  padding: 10px 14px;
  background: var(--sign-green);
  border: 0;
  border-radius: var(--radius-control);
  color: var(--surface);
  font-weight: 600;
  transition: background-color 150ms ease, transform 160ms var(--ease-out);
}
.submit:hover:not(:disabled), .again:hover { background: var(--sign-green-dark); }
.submit:active:not(:disabled), .again:active { transform: scale(0.98); }
.submit:disabled { background: #c9d2cd; color: #47534e; cursor: not-allowed; }
.done { display: grid; gap: 8px; justify-items: start; padding-top: 8px; }
.done-icon { display: grid; place-items: center; width: 48px; height: 48px; background: var(--sign-green-soft); border-radius: 50%; color: var(--sign-green-dark); }
.again { margin-top: 6px; padding-inline: 18px; }
</style>
