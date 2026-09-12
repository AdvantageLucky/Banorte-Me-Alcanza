import React, { useState, useEffect } from 'react';

const PHRASES = [
    "Escribe tu primer mensaje para empezar ; )",
    "Pregúntame lo que necesites...",
    "¡Hola! ¿En qué te puedo ayudar hoy?"
];

const Typewriter = () => {
    const [text, setText] = useState("");
    const [isDeleting, setIsDeleting] = useState(false);
    const [loopNum, setLoopNum] = useState(0);

    useEffect(() => {
        const currentPhrase = PHRASES[loopNum % PHRASES.length];

        // Velocidades: más rápido al borrar, pausa larga al terminar de escribir
        const typingSpeed = isDeleting ? 50 : 100;
        const pauseTime = text === currentPhrase && !isDeleting ? 2000 : typingSpeed;

        const timeout = setTimeout(() => {
            if (!isDeleting && text === currentPhrase) {
                // Terminó de escribir, pausar y luego borrar
                setIsDeleting(true);
            } else if (isDeleting && text === "") {
                // Terminó de borrar, pasar a la siguiente frase
                setIsDeleting(false);
                setLoopNum(loopNum + 1);
            } else {
                // Escribir o borrar la siguiente letra
                const nextCharLength = isDeleting ? text.length - 1 : text.length + 1;
                setText(currentPhrase.substring(0, nextCharLength));
            }
        }, pauseTime);

        return () => clearTimeout(timeout);
    }, [text, isDeleting, loopNum]);

    return (
        <p className="chat-empty">
            {text}
            <span className="cursor">|</span>
        </p>
    );
};

export default Typewriter;