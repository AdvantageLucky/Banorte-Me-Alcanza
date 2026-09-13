// Extrae el título y la descripción de la tarjeta A2UI que el backend arma
// para una sugerencia (ver sugerencias_a2ui.py). No duplica ese copy: lo lee
// de los mismos componentes 'titulo'/'descripcion' que ya se le muestran al
// usuario en la tarjeta, para que el modal de "Atender" nunca diga algo
// distinto a lo que la tarjeta ya mostró.
export function extractTituloDescripcion(a2uiJson) {
  if (!Array.isArray(a2uiJson)) {
    return { titulo: '', descripcion: '' };
  }
  const mensaje = a2uiJson.find((m) => m.updateComponents);
  const components = mensaje?.updateComponents?.components || [];
  const titulo = components.find((c) => c.id === 'titulo')?.text || '';
  const descripcion = components.find((c) => c.id === 'descripcion')?.text || '';
  return { titulo, descripcion };
}
