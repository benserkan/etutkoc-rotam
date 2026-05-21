import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// =============================================================================
// LGS özel ESLint kuralları — Dalga 0 anayasal kurallar
//
// 3 custom rule + bir adet built-in rule kombinasyonu:
//   1. lgs/no-bare-fetch        → fetch() yalnız lib/api.ts içinde, başka yerde YASAK
//                                  (R-007 cache yasağı + lib/api.ts wrapper'ın atlanması yasak)
//   2. lgs/missing-invalidate   → useMutation onSuccess'inde applyInvalidate yoksa uyar
//                                  (R-006 OOB swap kaybı önlemi)
//   3. lgs/no-bare-jargon       → JSX text'inde "DAU/MAU/MRR/ARPA/Churn/Tenant/NPS/LTV/CAC"
//                                  açıklamasız geçemez — JargonTooltip ile sarmalı
//                                  ([[feedback_admin_panel_jargon]])
// =============================================================================

/** @type {import('eslint').ESLint.Plugin} */
const lgsPlugin = {
  rules: {
    "no-bare-fetch": {
      meta: {
        type: "problem",
        docs: {
          description:
            "fetch() lib/api.ts wrapper'ından geçmeli — cache: 'no-store' default'unu atlama yasak",
        },
        schema: [],
        messages: {
          bareFetch:
            "Direkt fetch() yasak. `import { api } from '@/lib/api'` veya `apiServer` kullan. (R-007 cache yasağı)",
        },
      },
      create(context) {
        return {
          CallExpression(node) {
            if (node.callee.type === "Identifier" && node.callee.name === "fetch") {
              context.report({ node, messageId: "bareFetch" });
            }
          },
        };
      },
    },

    "missing-invalidate": {
      meta: {
        type: "suggestion",
        docs: {
          description:
            "useMutation onSuccess'inde applyInvalidate / invalidateQueries / clear çağrısı olmalı",
        },
        schema: [],
        messages: {
          missing:
            "useMutation onSuccess `applyInvalidate(qc, ...)` veya `qc.clear()` çağırmıyor — cache bayatlama riski (R-007). Gerekmiyorsa yorum satırı ile sus.",
        },
      },
      create(context) {
        return {
          CallExpression(node) {
            if (
              node.callee.type !== "Identifier" ||
              node.callee.name !== "useMutation"
            ) {
              return;
            }
            const arg = node.arguments?.[0];
            if (!arg || arg.type !== "ObjectExpression") return;

            // Object body'sini metin olarak tara
            const sourceCode = context.sourceCode ?? context.getSourceCode();
            const text = sourceCode.getText(arg);

            // Kabul edilen yan etki çağrıları (cache'i yönetiyorsa OK):
            //   applyInvalidate, invalidateOnSuccess, invalidateQueries,
            //   qc.clear(), queryClient.clear()
            const ALLOWED = /(applyInvalidate|invalidateOnSuccess|invalidateQueries|\.\s*clear\s*\()/;
            if (ALLOWED.test(text)) return;

            context.report({ node, messageId: "missing" });
          },
        };
      },
    },

    "no-bare-jargon": {
      meta: {
        type: "suggestion",
        docs: {
          description:
            "Admin panel jargonu (DAU/MRR/Churn/ARPA/NPS/LTV/CAC/Tenant/Descending) açıklamasız JSX text'te yer ALAMAZ",
        },
        schema: [],
        messages: {
          jargon:
            'Açıklamasız jargon "{{term}}" — `<JargonTooltip term="{{term}}" content="..." />` ile sar veya Türkçe karşılığını yaz.',
        },
      },
      create(context) {
        // Bilinçli olarak kısa liste — false positive'leri sınırlamak için.
        const JARGON = [
          "DAU", "WAU", "MAU",
          "MRR", "ARR", "ARPA",
          "Churn", "NPS", "LTV", "CAC", "ROI",
          "Tenant", "Descending", "Ascending",
        ];
        const re = new RegExp(`\\b(${JARGON.join("|")})\\b`);

        return {
          JSXText(node) {
            const m = node.value.match(re);
            if (m) {
              context.report({
                node,
                messageId: "jargon",
                data: { term: m[1] },
              });
            }
          },
        };
      },
    },
  },
};

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,

  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated codegen artifact'i — kontrol etme
    "lib/types/api.d.ts",
    // OpenAPI dump — generated
    "openapi.v2.json",
  ]),

  // LGS plugin'i tüm dosyalara uygula
  {
    plugins: { lgs: lgsPlugin },
    rules: {
      "lgs/no-bare-fetch": "error",
      "lgs/missing-invalidate": "warn",
      "lgs/no-bare-jargon": "warn",
    },
  },

  // İstisnalar: lib/api.ts, lib/api-server.ts, BFF route'ları fetch kullanır
  {
    files: [
      "lib/api.ts",
      "lib/api-server.ts",
      "app/api/**/route.ts",
    ],
    rules: {
      "lgs/no-bare-fetch": "off",
    },
  },
]);

export default eslintConfig;
