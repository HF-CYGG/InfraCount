# InfraCount Web（Vue3 + Vite + TypeScript）

本目录是 **单页应用（SPA）骨架**，用于逐步替换/迁移仓库根目录下的旧版模板页面（`templates/*.html`）。

## 目录与构建产物

- 源码目录：`web/src`
- 构建输出目录：`static/spa`
  - 由 [vite.config.ts](file:///E:/InfraCount/web/vite.config.ts) 的 `build.outDir` 控制
  - 后端 FastAPI 会在 `/spa` 路径下托管该目录（见 [main.py](file:///E:/InfraCount/api/main.py) 的 SPA 托管代码）

## 开发

```bash
cd web
npm install
npm run dev
```

开发态访问：
- http://localhost:5173/spa/

说明：
- 开发态已配置 `/api` 代理到 `http://localhost:8000`，用于避免跨域与 Cookie（登录态）问题。

## 构建

```bash
cd web
npm run build
```

构建后访问：
- 启动后端（例如 `uvicorn api.main:app --reload --port 8000`）
- 打开 http://localhost:8000/spa/

