// Extrae el título y un resumen de texto de la tarjeta A2UI que el backend
// arma para una sugerencia (ver sugerencias_a2ui.py). No duplica ese copy:
// el resumen se recombina del mismo StatCard (id 'stat') que ya se le
// muestra al usuario en la tarjeta del feed, para que el modal de "Atender"
// nunca diga algo distinto a lo que la tarjeta ya mostró. Si la tarjeta trae
// un Text 'descripcion' en vez de un StatCard (compatibilidad con tarjetas
// más simples), se usa ese texto tal cual.
export function extractTituloDescripcion(a2uiJson) {
  if (!Array.isArray(a2uiJson)) {
    return { titulo: '', descripcion: '' };
  }
  const mensaje = a2uiJson.find((m) => m.updateComponents);
  const components = mensaje?.updateComponents?.components || [];
  const titulo = components.find((c) => c.id === 'titulo')?.text || '';
  const stat = components.find((c) => c.id === 'stat' && c.component === 'StatCard');
  if (stat) {
    const descripcion = [stat.value, stat.trendLabel].filter(Boolean).join(' — ');
    return { titulo, descripcion };
  }
  const descripcion = components.find((c) => c.id === 'descripcion')?.text || '';
  return { titulo, descripcion };
}
