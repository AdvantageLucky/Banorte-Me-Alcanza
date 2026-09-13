import { BarChart3, Sparkles } from 'lucide-react';
import Typewriter from './typewritter.jsx';
import logo from '../assets/images/logo.svg';

// Dos sugerencias fijas para invitar a arrancar la conversación: mismo
// texto que se manda si el usuario las escribiera a mano, así que
// simplemente reusan submitMensaje (ver AsistenteView) como si fueran un
// envío normal del formulario.
const SUGERENCIAS = [
  {
    Icon: BarChart3,
    iconClass: 'asistente-suggestion-icon-chart',
    titulo: 'Analizar mis recibos',
    descripcion: 'Calcula el impacto de tus próximos pagos.',
    texto: 'Analizar mis recibos de este mes',
  },
  {
    Icon: Sparkles,
    iconClass: 'asistente-suggestion-icon-sparkles',
    titulo: '¿Me alcanza?',
    descripcion: 'Proyecta tu saldo disponible tras cubrir tus gastos.',
    texto: '¿Me alcanza para pagar la luz y el agua?',
  },
];

// Bienvenida que reemplaza la única línea de texto que había antes de
// mandar el primer mensaje. Se muestra con la misma condición que ya usaba
// el Typewriter solo (ver AsistenteView), y lo sigue usando tal cual como
// título animado — solo le suma mascota y tarjetas de sugerencia alrededor.
export default function AsistenteEmptyState({ onSugerencia }) {
  return (
    <div className="asistente-empty">
      <img className="asistente-empty-avatar" src={logo} alt="" width="72" height="72" />
      <Typewriter />
      <p className="asistente-empty-subtitulo" style={{ marginBottom: 0 }}>
        Escribe tu consulta o elige una de las opciones sugeridas.
      </p>
      <p className="asistente-empty-subtitulo" style={{ color: 'var(--a2ui-color-gray-500)' }}>
        Conoce a Banorberto :D
      </p>
      <div className="asistente-suggestions">
        {SUGERENCIAS.map(({ Icon, iconClass, titulo, descripcion, texto }) => (
          <button
            key={titulo}
            type="button"
            className="asistente-suggestion-card"
            onClick={() => onSugerencia(texto)}
          >
            <span className="asistente-suggestion-titulo">
              <span className={`asistente-suggestion-icon ${iconClass}`}>
                <Icon size={18} />
              </span>
              {titulo}
            </span>
            <span className="asistente-suggestion-desc">{descripcion}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
