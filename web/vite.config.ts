/**
 * Vite 配置文件
 *
 * 目标：
 * 1) 开发态：提供 Vue3 + TS 的本地开发服务器，并把 /api 代理到后端 FastAPI（避免跨域与 Cookie 受限问题）。
 * 2) 生产态：构建产物输出到后端可直接托管的目录：../static/spa
 *    - 这样 FastAPI 只需把 static/spa 下的 index.html + assets 静态文件暴露出来即可。
 * 3) base 设置为 /spa/：
 *    - 使得资源引用路径固定为 /spa/assets/...，便于后端挂载到 /spa 路径下托管。
 */

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";

export default defineConfig(() => {
  return {
    plugins: [vue()],
    base: "/spa/",
    resolve: {
      /**
       * 路径别名
       * - 让我们可以用 @/xxx 来引用 src 下的文件，代码更清爽；
       * - 同时与 tsconfig.json 的 paths 保持一致。
       */
      alias: {
        "@": path.resolve(__dirname, "src")
      }
    },
    build: {
      /**
       * outDir 指向仓库根目录的 static/spa
       * - 注意：Vite 的 outDir 必须是绝对路径，这里用 path.resolve 生成。
       */
      outDir: path.resolve(__dirname, "..", "static", "spa"),
      /**
       * emptyOutDir 会清空 outDir 目录（仅清空 static/spa，不会影响 static 的其它目录）
       * - 便于每次构建获得干净产物，避免老资源残留导致的缓存问题。
       */
      emptyOutDir: true,
      /**
       * assetsDir 用于放置打包后的 JS/CSS/图片等资源
       * - 保持为 assets，便于后端 Nginx/CDN 等规则配置。
       */
      assetsDir: "assets"
    },
    server: {
      /**
       * 开发模式下代理 /api 到 FastAPI
       * - 浏览器看到的请求仍然是 http://localhost:5173/api/...
       * - 由 Vite 代理转发到 http://localhost:8000/api/...
       * - Cookie 以 localhost:5173 为域写入，后续同样通过代理携带转发给后端，开发体验更顺滑。
       */
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true
        }
      }
    }
  };
});
