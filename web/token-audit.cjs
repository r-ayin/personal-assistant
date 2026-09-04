#!/usr/bin/env node
/**
 * 临时 token 审计：扫描 web/ 应用代码里所有 var(--x) 引用与 globals.css 的所有定义，
 * 报告未定义引用。带兜底值的 var(--x, fallback) 与 --phase 类局部变量豁免。
 * 审计完即删。
 */
const fs = require("fs");
const path = require("path");

const ROOT = __dirname;

function* walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name === "dist" || e.name.startsWith(".")) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (/\.(tsx?|css)$/.test(e.name)) yield p;
  }
}

// 1) 定义：app/globals.css（运行时唯一被 import 的样式真源）
const globals = fs.readFileSync(path.join(ROOT, "app/globals.css"), "utf8");
const defined = new Set();
for (const m of globals.matchAll(/(--[\w-]+)\s*:/g)) defined.add(m[1]);

// 2) 引用：app/ components/ lib/ 下的 tsx/ts/css
const undef = [];
let total = 0;
for (const dir of ["app", "components", "lib"]) {
  for (const file of walk(path.join(ROOT, dir))) {
    const src = fs.readFileSync(file, "utf8");
    for (const m of src.matchAll(/var\(\s*(--[\w-]+)\s*(,[^)]*)?\)/g)) {
      total++;
      const name = m[1];
      const hasFallback = !!m[2];
      if (!defined.has(name) && !hasFallback) {
        const line = src.slice(0, m.index).split("\n").length;
        undef.push(`${path.relative(ROOT, file)}:${line} ${name}`);
      }
    }
  }
}

console.log(`defined in app/globals.css :root → ${defined.size} tokens`);
console.log(`var(--x) references scanned → ${total}`);
if (undef.length === 0) {
  console.log("UNDEFINED REFERENCES: 0 ✓");
} else {
  console.log(`UNDEFINED REFERENCES: ${undef.length}`);
  for (const u of undef) console.log("  " + u);
  process.exitCode = 1;
}
