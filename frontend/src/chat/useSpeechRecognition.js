import { useEffect, useMemo, useRef, useState } from 'react';

// Dictado por voz (STT) para accesibilidad: envuelve la Web Speech API
// nativa del navegador (sin dependencias nuevas, sin backend). Chrome/Edge
// la traen completa como `webkitSpeechRecognition`; Safari tiene soporte
// parcial y Firefox no la trae — por eso todo el hook es opt-in y expone
// `supported` para que el llamador oculte el botón de mic si no aplica.
//
// onFinalResult(texto) se dispara cuando el usuario termina de hablar (el
// propio navegador detecta el silencio y cierra el reconocimiento), no en
// cada resultado intermedio — así el caller puede autoenviar el mensaje.
export function useSpeechRecognition({ lang = 'es-MX', onFinalResult } = {}) {
  const [listening, setListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const recognitionRef = useRef(null);
  const onFinalResultRef = useRef(onFinalResult);
  onFinalResultRef.current = onFinalResult;

  const SpeechRecognitionCtor = useMemo(
    () =>
      typeof window !== 'undefined'
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null,
    [],
  );
  const supported = Boolean(SpeechRecognitionCtor);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  function start() {
    if (!supported || listening) {
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = lang;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let finalText = '';
      let interimText = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }
      if (finalText) {
        onFinalResultRef.current?.(finalText.trim());
      }
      setInterimTranscript(interimText);
    };
    recognition.onerror = () => {
      setListening(false);
      setInterimTranscript('');
    };
    recognition.onend = () => {
      setListening(false);
      setInterimTranscript('');
    };
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  function stop() {
    recognitionRef.current?.stop();
  }

  return { supported, listening, interimTranscript, start, stop };
}
