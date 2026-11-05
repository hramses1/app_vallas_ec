// Prueba el formato de textos: node web/e2e/format_check.mjs
import assert from 'node:assert/strict'
import { prettyName } from '../src/format.js'

assert.equal(prettyName('GRANCOMERCIO CIA LTDA'), 'Grancomercio Cía. Ltda.')
assert.equal(prettyName('ZAZACORP S.A'), 'Zazacorp S.A.')
assert.equal(prettyName('AV. AGUSTIN FREIRE E ISIDRO AYORA, LADO A'), 'Av. Agustin Freire e Isidro Ayora, lado A')
assert.equal(prettyName('S-00508 / AV. PABLO PALACIOS'), 'Av. Pablo Palacios')
assert.equal(prettyName('VIA DURAN KM 0.8 (SENTIDO 2)'), 'Via Duran km 0.8 (sentido 2)')
assert.equal(prettyName('OSWALDO GUAYASAMIN (N-S)'), 'Oswaldo Guayasamin (N-S)')
// Lo que ya tiene minúsculas no se toca
assert.equal(prettyName('Av. Juan Tanca Marengo, frente a Mall del Sol'), 'Av. Juan Tanca Marengo, frente a Mall del Sol')
assert.equal(prettyName(''), '')
console.log('ok')
