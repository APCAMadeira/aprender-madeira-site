// Configuração do site Aprender Madeira (Astro, site estático).
// O endereço final é definido pela variável SITE_URL no servidor.
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: process.env.SITE_URL || 'https://teste.aprenderamadeira.net',
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});
