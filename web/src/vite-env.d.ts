/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

/**
 * Vite 类型声明文件
 *
 * 作用：
 * - 让 TypeScript 认识 import.meta.env 等 Vite 注入的类型；
 * - 避免在 IDE 中出现 “Property 'env' does not exist on type ImportMeta” 一类报错。
 */

