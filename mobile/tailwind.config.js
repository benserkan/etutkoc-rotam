/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // "J" platform dili (2026-10-29, web ile aynı): zemin beyaz, kart
        // beyaz, çerçeve görünür gri. Ekranlar bg-slate-50 zemin + border-slate-200
        // kart çizgisiyle yazıldığı için bu iki ton merkezden J değerlerine çekilir.
        slate: {
          ...require("tailwindcss/colors").slate,
          50: "#FAFAFB",
          100: "#F4F4F6",
          200: "#CBCBCD",
          400: "#737782", // ikincil gri metin (tarih, alt satır) bir tık koyu
          500: "#565A64", // soluk metin bir tık koyu (web ile aynı)
          600: "#3F434C",
        },
        // ETÜTKOÇ marka paleti (web ile tutarlı)
        brand: {
          DEFAULT: "#0e7490", // cyan-700 (petrol)
          50: "#ecfeff",
          100: "#cffafe",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
          800: "#155e75",
          900: "#134e4a",
        },
        gold: {
          DEFAULT: "#E8AC2D",
          500: "#f59e0b",
          600: "#d97706",
        },
      },
    },
  },
  plugins: [],
};
