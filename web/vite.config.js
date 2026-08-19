import { defineConfig } from "vite";

// The application is served from the FastAPI root, so asset URLs are relative
// to the server root. It used to be mounted under /workbench alongside a
// separate landing page; that page was documentation about the build rather
// than the product, and /workbench now redirects here.
export default defineConfig({
  base: "/",
});
