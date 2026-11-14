/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/app/**/*.{js,jsx}", "./src/components/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#173326",
        forest: "#176a43",
        green: "#238754",
        mint: "#e9f5e9",
        sage: "#f0f6ef",
        paper: "#fbfcfa",
        amber: "#f3d56b",
        peach: "#fff0df"
      }
    }
  },
  plugins: []
};
