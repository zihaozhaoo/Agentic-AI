import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
  assetsInclude: ['**/*.yaml', '**/*.yml'],
  envDir: '../../', // Root of repo
	optimizeDeps: {
		exclude: ['@lucide/svelte']
	},
	server: {
    proxy: {
      '/api': {
        target: 'http://localhost:39000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/ws': {
        target: 'ws://localhost:39000',
        ws: true,
        changeOrigin: true,
        secure: false
      }
    }
  }
});
