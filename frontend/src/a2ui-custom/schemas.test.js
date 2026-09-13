import { describe, it, expect } from 'vitest';
import { StatCardApi, BarChartApi, PlanDePagoApi, LineChartApi, ApartadoPlannerApi } from './schemas.js';

describe('StatCardApi', () => {
  it('acepta un valor literal y un binding para label/value', () => {
    const result = StatCardApi.schema.safeParse({
      label: 'Salud financiera',
      value: '82/100',
      trend: 'up',
      trendLabel: 'Mejoró vs el mes pasado',
      tone: 'positive',
    });
    expect(result.success).toBe(true);
  });

  it('acepta value enlazado a un path del data model', () => {
    const result = StatCardApi.schema.safeParse({
      label: { path: '/saldoLabel' },
      value: { path: '/saldoValue' },
    });
    expect(result.success).toBe(true);
  });

  it('rechaza props desconocidas (.strict())', () => {
    const result = StatCardApi.schema.safeParse({
      label: 'x',
      value: 'y',
      colorFavorito: 'rojo',
    });
    expect(result.success).toBe(false);
  });

  it('rechaza sin label/value requeridos', () => {
    const result = StatCardApi.schema.safeParse({ trend: 'up' });
    expect(result.success).toBe(false);
  });
});

describe('BarChartApi', () => {
  it('acepta bars con datos reales', () => {
    const result = BarChartApi.schema.safeParse({
      title: 'Gastos por categoría',
      valuePrefix: '$',
      bars: [
        { label: 'Renta', value: 8000 },
        { label: 'Transporte', value: 1200, tone: 'warning' },
      ],
    });
    expect(result.success).toBe(true);
  });

  it('rechaza bars vacío', () => {
    const result = BarChartApi.schema.safeParse({ bars: [] });
    expect(result.success).toBe(false);
  });

  it('rechaza una barra sin value', () => {
    const result = BarChartApi.schema.safeParse({ bars: [{ label: 'Renta' }] });
    expect(result.success).toBe(false);
  });
});

describe('PlanDePagoApi', () => {
  it('acepta options con selectedId enlazado a un path', () => {
    const result = PlanDePagoApi.schema.safeParse({
      title: 'Elige tu plan',
      options: [
        { id: 'sugerido', label: 'Semanal', detail: '8 periodos', amount: '$125.00', highlighted: true },
      ],
      selectedId: { path: '/planSeleccionado' },
    });
    expect(result.success).toBe(true);
  });

  it('rechaza sin selectedId', () => {
    const result = PlanDePagoApi.schema.safeParse({
      options: [{ id: 'a', label: 'A', detail: 'd', amount: '$1.00' }],
    });
    expect(result.success).toBe(false);
  });

  it('rechaza una opción sin amount', () => {
    const result = PlanDePagoApi.schema.safeParse({
      options: [{ id: 'a', label: 'A', detail: 'd' }],
      selectedId: 'a',
    });
    expect(result.success).toBe(false);
  });
});

describe('LineChartApi', () => {
  it('acepta una serie con al menos 2 puntos', () => {
    const result = LineChartApi.schema.safeParse({
      title: 'Proyección de saldo',
      valuePrefix: '$',
      points: [
        { label: '11 sep', value: 500 },
        { label: '15 sep', value: -570, tone: 'negative' },
      ],
      thresholdValue: 0,
      thresholdLabel: 'Saldo en $0',
    });
    expect(result.success).toBe(true);
  });

  it('rechaza una serie con un solo punto', () => {
    const result = LineChartApi.schema.safeParse({
      points: [{ label: '11 sep', value: 500 }],
    });
    expect(result.success).toBe(false);
  });

  it('rechaza sin points', () => {
    const result = LineChartApi.schema.safeParse({ title: 'x' });
    expect(result.success).toBe(false);
  });
});

describe('ApartadoPlannerApi', () => {
  it('acepta montoPorPeriodo enlazado a un path', () => {
    const result = ApartadoPlannerApi.schema.safeParse({
      title: 'Ajusta tu apartado',
      montoObjetivo: 570,
      periodicidadLabel: 'semanal',
      minMonto: 50,
      maxMonto: 300,
      montoPorPeriodo: { path: '/montoPorPeriodo' },
    });
    expect(result.success).toBe(true);
  });

  it('acepta montoPorPeriodo como literal', () => {
    const result = ApartadoPlannerApi.schema.safeParse({
      montoObjetivo: 570,
      periodicidadLabel: 'semanal',
      minMonto: 50,
      maxMonto: 300,
      montoPorPeriodo: 142.5,
    });
    expect(result.success).toBe(true);
  });

  it('rechaza sin montoObjetivo', () => {
    const result = ApartadoPlannerApi.schema.safeParse({
      periodicidadLabel: 'semanal',
      minMonto: 50,
      maxMonto: 300,
      montoPorPeriodo: { path: '/montoPorPeriodo' },
    });
    expect(result.success).toBe(false);
  });
});
