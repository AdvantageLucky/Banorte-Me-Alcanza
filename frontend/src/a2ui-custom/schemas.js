import { z } from 'zod';

// GenericBinder (@a2ui/web_core) detecta un campo "dinámico" (enlazable a un
// path del data model) inspeccionando la FORMA del ZodUnion: uno de sus
// miembros debe ser un objeto con 'path' y sin 'componentId'. No necesitamos
// reusar los helpers internos de @a2ui/web_core (no son públicos) — basta con
// replicar esa forma.
const DataBinding = z.object({ path: z.string() });

export const DynamicString = z.union([z.string(), DataBinding]);

const ToneEnum = z.enum(['positive', 'negative', 'neutral', 'warning']);

export const StatCardApi = {
  name: 'StatCard',
  schema: z
    .object({
      weight: z.number().optional(),
      label: DynamicString,
      value: DynamicString,
      trend: z.enum(['up', 'down', 'flat']).optional(),
      trendLabel: DynamicString.optional(),
      tone: ToneEnum.default('neutral').optional(),
    })
    .strict(),
};

export const BarChartApi = {
  name: 'BarChart',
  schema: z
    .object({
      weight: z.number().optional(),
      title: DynamicString.optional(),
      valuePrefix: z.string().optional(),
      bars: z
        .array(
          z
            .object({
              label: z.string(),
              value: z.number(),
              tone: ToneEnum.optional(),
            })
            .strict(),
        )
        .min(1),
    })
    .strict(),
};

export const PlanDePagoApi = {
  name: 'PlanDePago',
  schema: z
    .object({
      weight: z.number().optional(),
      title: DynamicString.optional(),
      subtitle: DynamicString.optional(),
      options: z
        .array(
          z
            .object({
              id: z.string(),
              label: z.string(),
              detail: z.string(),
              amount: z.string(),
              highlighted: z.boolean().optional(),
            })
            .strict(),
        )
        .min(1),
      selectedId: DynamicString,
    })
    .strict(),
};
