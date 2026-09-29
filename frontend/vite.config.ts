import pyodidePackage from "pyodide/package.json";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { configDefaults, defineConfig } from "vitest/config";

const runtimeEnv = (
  globalThis as typeof globalThis & {
    process?: { env?: Record<string, string | undefined> };
  }
).process?.env;

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    viteStaticCopy({
      targets: [
        {
          src: "node_modules/pyodide/{pyodide.mjs,pyodide.asm.js,pyodide.asm.wasm,python_stdlib.zip,pyodide-lock.json}",
          dest: `pyodide/${pyodidePackage.version}`,
          rename: { stripBase: true }
        }
      ]
    })
  ],
  optimizeDeps: {
    exclude: ["pyodide"]
  },
  server: {
    proxy: {
      "/api": {
        target: runtimeEnv?.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  build: {
    // Mermaid's generated parser is one lazy-loaded third-party module
    // (currently about 663 kB) that cannot be split internally. Keep the
    // warning just above that measured boundary so future growth remains
    // visible while the initial and other optional chunks stay actionable.
    chunkSizeWarningLimit: 680,
    // Keep heavyweight optional capabilities out of the route and shared
    // chunks. These groups are deliberately package-based so a dependency
    // upgrade cannot silently pull a new feature into the initial bundle.
    rolldownOptions: {
      output: {
        // Manual library groups can form cross-chunk cycles. Preserve module
        // initialization order for CodeMirror, Mermaid and shared dependencies.
        strictExecutionOrder: true,
        // Leave Markmap on automatic splitting: separating its browser facade
        // from plugin initializers creates a cycle that fails only in production.
        codeSplitting: {
          groups: [
            {
              name: "echarts",
              test: /node_modules[\\/]echarts[\\/]/,
              priority: 30,
              minSize: 8 * 1024,
              maxSize: 320 * 1024,
              entriesAware: false,
              includeDependenciesRecursively: false
            },
            {
              name: "mermaid",
              test: /node_modules[\\/]mermaid[\\/]/,
              priority: 30,
              minSize: 8 * 1024,
              maxSize: 320 * 1024,
              entriesAware: false,
              includeDependenciesRecursively: false
            },
            {
              name: "mermaid-parser",
              test: (moduleId) => moduleId.includes("@mermaid-js") && moduleId.includes("parser"),
              priority: 30,
              minSize: 8 * 1024,
              maxSize: 320 * 1024,
              entriesAware: false,
              includeDependenciesRecursively: false
            },
            {
              name: "code-editor",
              test: /node_modules[\\/](@codemirror|@uiw)[\\/]/,
              priority: 30,
              minSize: 8 * 1024,
              maxSize: 260 * 1024,
              entriesAware: false,
              includeDependenciesRecursively: false
            },
            {
              name: "graph-runtime",
              test: /node_modules[\\/]cytoscape[\\/]/,
              priority: 30,
              minSize: 8 * 1024,
              maxSize: 260 * 1024,
              entriesAware: false,
              includeDependenciesRecursively: false
            },
            {
              name: "math-rendering",
              test: /node_modules[\\/]katex[\\/]/,
              priority: 20,
              minSize: 8 * 1024,
              maxSize: 260 * 1024,
              entriesAware: false,
              includeDependenciesRecursively: false
            }
          ]
        }
      }
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    testTimeout: 15_000,
    css: true,
    exclude: [...configDefaults.exclude, "e2e/**"]
  }
});
