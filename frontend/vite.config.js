import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  // 产物输出到仓库根 dist/：Dockerfile 与服务器部署路径保持不变
  build: { outDir: "../dist", emptyOutDir: true },
});
