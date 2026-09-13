import { formatFecha, formatMonto } from '../yo/formatters.js';

// Traduce {tipo, detalle} (tal como los arma sugerencias_engine.py en el
// backend) a un título + descripción en español. Cada regla de detección le
// da forma distinta a `detalle`, así que este mapeo es lo único que se
// rompería si el backend cambia esas formas — de ahí que tenga sus propios
// tests.
const BUILDERS = {
  riesgo_liquidez: ({ margen, fecha_critica: fechaCritica }) => ({
    titulo: 'Riesgo de saldo negativo',
    descripcion: `Tu saldo podría quedar en ${formatMonto(margen)} para el ${formatFecha(fechaCritica)}.`,
  }),
  gasto_fijo_proximo: ({ concepto, monto, proxima_fecha: proximaFecha }) => ({
    titulo: `Pago próximo: ${concepto}`,
    descripcion: `${formatMonto(monto)} vence el ${formatFecha(proximaFecha)} y es una parte importante de tu saldo actual.`,
  }),
  meta_en_riesgo: ({ descripcion, monto_objetivo: montoObjetivo, monto_ahorrado: montoAhorrado, fecha_objetivo: fechaObjetivo }) => ({
    titulo: `Meta en riesgo: ${descripcion}`,
    descripcion: `Llevas ${formatMonto(montoAhorrado)} de ${formatMonto(montoObjetivo)} y la fecha límite es el ${formatFecha(fechaObjetivo)}.`,
  }),
};

export function getSugerenciaCopy({ tipo, detalle }) {
  const builder = BUILDERS[tipo];
  if (!builder) {
    return { titulo: 'Sugerencia', descripcion: '' };
  }
  return builder(detalle);
}
