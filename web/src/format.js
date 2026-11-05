// Los datos del CNE llegan en mayúsculas y con códigos internos. Esto solo cambia cómo se muestran.
const SMALL_WORDS = new Set(['y', 'e', 'o', 'u', 'de', 'del', 'la', 'las', 'el', 'los', 'en', 'a', 'al', 'por', 'con', 'hacia', 'junto', 'frente', 'entre', 'desde', 'sentido', 'lado', 'diagonal', 'antes', 'después'])
const FIXED = {
  AV: 'Av.', 'AV.': 'Av.', KM: 'km', 'KM.': 'km', CIA: 'Cía.', 'CIA.': 'Cía.', LTDA: 'Ltda.', 'LTDA.': 'Ltda.',
  'S.A': 'S.A.', 'S.A.': 'S.A.', SA: 'S.A.', 'S.A.S': 'S.A.S.', SAS: 'S.A.S.', CC: 'C.C.', 'C.C': 'C.C.', 'C.C.': 'C.C.',
  CDLA: 'Cdla.', 'CDLA.': 'Cdla.', URB: 'Urb.', 'URB.': 'Urb.',
}
const ACRONYMS = new Set(['IESS', 'UPSE', 'CNT', 'ESPOCH', 'LED', 'GYE', 'VST', 'EC', 'UIO', 'CNE', 'FAE', 'TTG', 'LFC', 'OUTMEC', 'PUCE', 'KFC', 'UTE'])

function formatWord(word, isFirst, previous) {
  const fixed = FIXED[word]
  if (fixed) return fixed
  // "LADO A" y "CARA B" nombran una cara de la valla: la letra se queda en mayúscula
  if (/^(LADO|CARA)$/.test(previous) && /^[A-Z]\W*$/.test(word)) return word
  if (ACRONYMS.has(word.replace(/[^\p{L}]/gu, ''))) return word
  // Sentidos y referencias cortas como N-S o A-1 se quedan igual
  if (/^\(?[\p{L}\d]{1,2}-[\p{L}\d]{1,2}\)?,?$/u.test(word)) return word
  const lower = word.toLocaleLowerCase('es')
  if (!isFirst && SMALL_WORDS.has(lower.replace(/[^\p{L}]/gu, ''))) return lower
  return lower.replace(/\p{L}/u, (letter) => letter.toLocaleUpperCase('es'))
}

export function prettyName(text) {
  if (!text) return ''
  const clean = text.replace(/^S-\d+\s*\/\s*/, '').trim()
  const letters = clean.replace(/[^\p{L}]/gu, '')
  const uppercase = letters.replace(/[^\p{Lu}]/gu, '')
  // Lo que ya viene escrito con mayúsculas y minúsculas se respeta
  if (!letters || uppercase.length / letters.length < 0.7) return clean
  const words = clean.split(/\s+/)
  return words.map((word, index) => formatWord(word, index === 0, words[index - 1])).join(' ')
}
