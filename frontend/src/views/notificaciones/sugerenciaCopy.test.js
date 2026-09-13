import { describe, it, expect } from 'vitest';
import { getSugerenciaCopy } from './sugerenciaCopy.js';

describe('getSugerenciaCopy', () => {
  it('arma el copy de riesgo_liquidez con el margen y la fecha crítica', () => {
    const copy = getSugerenciaCopy({
      tipo: 'riesgo_liquidez',
      detalle: { margen: -450.5, fecha_critica: '2026-09-20', saldo_minimo_proyectado: -450.5 },
    });

    expect(copy.titulo).toBe('Riesgo de saldo negativo');
    expect(copy.descripcion).toContain('20 sep');
    expect(copy.descripcion).toContain('$450.50');
  });

  it('arma el copy de gasto_fijo_proximo con el concepto y el monto', () => {
    const copy = getSugerenciaCopy({
      tipo: 'gasto_fijo_proximo',
      detalle: { concepto: 'Renta', monto: 5000, proxima_fecha: '2026-09-15' },
    });

    expect(copy.titulo).toBe('Pago próximo: Renta');
    expect(copy.descripcion).toContain('$5,000.00');
    expect(copy.descripcion).toContain('15 sep');
  });

  it('arma el copy de meta_en_riesgo con el progreso y la fecha objetivo', () => {
    const copy = getSugerenciaCopy({
      tipo: 'meta_en_riesgo',
      detalle: { descripcion: 'Viaje', monto_objetivo: 1000, monto_ahorrado: 200, fecha_objetivo: '2026-10-01' },
    });

    expect(copy.titulo).toBe('Meta en riesgo: Viaje');
    expect(copy.descripcion).toContain('$200.00');
    expect(copy.descripcion).toContain('$1,000.00');
  });

  it('devuelve un copy genérico para un tipo desconocido en vez de fallar', () => {
    const copy = getSugerenciaCopy({ tipo: 'algo_nuevo', detalle: {} });

    expect(copy.titulo).toBe('Sugerencia');
    expect(copy.descripcion).toBe('');
  });
});
