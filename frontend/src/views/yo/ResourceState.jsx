// Envoltura común de loading / error-con-reintentar / vacío para las
// pestañas de "Yo". Cada pestaña solo decide cómo se ve un item cuando sí
// hay datos.
export default function ResourceState({ loading, error, reload, isEmpty, emptyMessage, children }) {
  if (loading) {
    return <p className="yo-state yo-state-loading">Cargando...</p>;
  }
  if (error) {
    return (
      <div className="yo-state yo-state-error">
        <p>{error}</p>
        <button type="button" onClick={reload}>
          Reintentar
        </button>
      </div>
    );
  }
  if (isEmpty) {
    return <p className="yo-state yo-state-empty">{emptyMessage}</p>;
  }
  return children;
}
