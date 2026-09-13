import { useEffect, useMemo, useState } from 'react';

// Lectura en voz alta (TTS) para accesibilidad: envuelve
// `window.speechSynthesis`, nativo del navegador (sin dependencias nuevas,
// sin backend ni costos de un servicio de voz). Soportado en
// Chrome/Edge/Safari/Firefox modernos.
export function useSpeechSynthesis({ lang = 'es-MX' } = {}) {
  const [speakingId, setSpeakingId] = useState(null);
  const supported = useMemo(
    () => typeof window !== 'undefined' && 'speechSynthesis' in window,
    [],
  );

  useEffect(() => {
    return () => {
      if (supported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [supported]);

  function speak(text, id) {
    if (!supported || !text) {
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.onend = () => setSpeakingId((current) => (current === id ? null : current));
    utterance.onerror = () => setSpeakingId((current) => (current === id ? null : current));
    setSpeakingId(id);
    window.speechSynthesis.speak(utterance);
  }

  function cancel() {
    if (supported) {
      window.speechSynthesis.cancel();
    }
    setSpeakingId(null);
  }

  return { supported, speakingId, speak, cancel };
}
