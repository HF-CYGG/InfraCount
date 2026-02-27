/**
 * 应用入口文件
 *
 * 职责：
 * 1) 创建 Vue 应用实例；
 * 2) 挂载路由；
 * 3) 挂载到 index.html 的 #app 容器；
 * 4) 初始化全局样式。
 */

import { createApp } from "vue";
import App from "@/App.vue";
import { router } from "@/router";
import "@/styles/global.css";

const app = createApp(App);
app.use(router);
app.mount("#app");

