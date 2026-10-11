// Temp dev-server config for verifying in-repo fixes (NOT deployed).
// Same setup as the repo vite.config.ts but proxies /api to the LIVE
// port-forward (127.0.0.1:8080) so real data + WS are served.
import base from '../vite.config'
import { defineConfig, mergeConfig } from 'vite'

export default mergeConfig(
  base,
  defineConfig({
    server: {
      proxy: {
        '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      },
    },
  })
)
