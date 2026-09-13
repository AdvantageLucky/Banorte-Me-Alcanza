const PALETTE = {
    neutral: {
        white: '#ffffff',
        light: '#f8fafc', // background — antes #f5f5f5, mismo rol, tono frío tipo slate-50
        gray: '#e2e8f0',  // border — antes #c7c9c9, slate-200
        dark: '#0f172a',  // on-background, on-surface — antes #1f1f1f, slate-900
        muted: '#94a3b8', // texto secundario más claro (fechas, hints, labels pequeños)
    },
    brand: {
        primary: '#EB0029',     // antes #ec0029, prácticamente el mismo rojo Banorte
        primaryDark: '#B8001F', // hover/active de elementos primarios
        primarySoft: '#FFF1F2', // fondo tenue para resaltados y badges en rojo
        secondary: '#64748b',   // antes #6a6867, texto/borde secundario, tono slate-500
        tertiary: '#334155',    // antes #5b6570, burbuja de chat del usuario, slate-700
    },
    accent: {
        yellow: '#f8d44c',
        blue: '#108dcd',
    },
    state: {
        success: '#059669',
        warning: '#b45309',
        danger: '#c5221f',
    },
};

export const COLORS = Object.freeze({
    // Colores de marca
    primary: PALETTE.brand.primary,
    primaryDark: PALETTE.brand.primaryDark,
    primarySoft: PALETTE.brand.primarySoft,
    secondary: PALETTE.brand.secondary,

    // Fondos y Superficies
    background: PALETTE.neutral.light,
    surface: PALETTE.neutral.white,
    border: PALETTE.neutral.gray,
    input: PALETTE.neutral.white,
    messageUser: PALETTE.brand.tertiary,

    // Textos / Elementos "On" (sobre)
    onBackground: PALETTE.neutral.dark,
    onSurface: PALETTE.neutral.dark,
    onPrimary: PALETTE.neutral.white,
    onSecondary: PALETTE.neutral.white,
    onInput: PALETTE.neutral.dark,
    textMuted: PALETTE.neutral.muted,

    // Estados (antes repartidos como hex sueltos en index.css / a2ui-custom)
    success: PALETTE.state.success,
    warning: PALETTE.state.warning,
    danger: PALETTE.state.danger,

    // Acentos
    accentYellow: PALETTE.accent.yellow,
    accentBlue: PALETTE.accent.blue,
});
