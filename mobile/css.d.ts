// CSS side-effect import'ları (NativeWind global.css) + web CSS module'leri.
declare module "*.css";
declare module "*.module.css" {
  const classes: { readonly [key: string]: string };
  export default classes;
}
