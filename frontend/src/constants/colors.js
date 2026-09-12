const PALETTE = {
    neutral: {
        white: '#ffffff',
        light: '#f5f5f5', // background
        gray: '#c7c9c9',  // border
        dark: '#1f1f1f',  // on-background, on-surface
    },
    brand: {
        primary: '#ec0029',
        secondary: '#6a6867',
        tertiary: '#5b6570',
    },
    accent: {
        yellow: '#f8d44c',
        blue: '#108dcd',
    },
};

export const COLORS = Object.freeze({
    // Colores de marca
    primary: PALETTE.brand.primary,
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

    // Acentos
    accentYellow: PALETTE.accent.yellow,
    accentBlue: PALETTE.accent.blue,
});