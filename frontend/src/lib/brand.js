const BRANDS = {
  bata: { key: "bata", name: "Bata", logo: "/bata-logo.svg", logoWhite: "/bata-logo-white.svg", hero: "/bata-store.jpg", accent: "#E60000", logoClass: "h-6", loginLogoClass: "h-9", weekLabel: "Bata weeks" },
  kazo: { key: "kazo", name: "KAZO", logo: "/kazo-logo.png", logoWhite: "/kazo-logo-white.png", hero: "/kazo-store.jpg", accent: "#111111", logoClass: "h-5", loginLogoClass: "h-8", weekLabel: "retail weeks" },
};

const q = new URLSearchParams(window.location.search).get("brand");
if (q && BRANDS[q]) localStorage.setItem("sis_brand", q);
if (q === "reset") localStorage.removeItem("sis_brand");
export const brand = BRANDS[localStorage.getItem("sis_brand")] || BRANDS.bata;
if (brand.key !== "bata") document.documentElement.classList.add(`brand-${brand.key}`);
