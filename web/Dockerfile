# =============================================================================
# Next.js standalone build — Lightsail Docker Compose içindeki `next` servisi
# Hedef boyut: <250MB (multi-stage, sadece runtime artifact'leri taşınır)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: deps — Tüm bağımlılıkları yükle (dev + prod, build için)
# -----------------------------------------------------------------------------
FROM node:22-alpine AS deps

# Alpine'da next.js ve native modüller için gerekli
RUN apk add --no-cache libc6-compat

WORKDIR /app

# pnpm'i corepack üzerinden aktive et — Node 22 dahili
RUN corepack enable && corepack prepare pnpm@11.1.2 --activate

# Bağımlılık manifestoları (kod değişimi onları etkilemediği sürece bu katman cache'lenir)
COPY package.json pnpm-lock.yaml ./

# Build için dev bağımlılıklarını da kur.
# --ignore-scripts: yeni pnpm, build script'i olan paketleri (sharp/msw/unrs-resolver)
# onaysız reddedip ERR_PNPM_IGNORED_BUILDS ile çöküyor. Bu paketler prebuilt binary
# kullanır (build script gerekmez) → scriptleri atlamak güvenli + deterministik.
RUN pnpm install --frozen-lockfile --ignore-scripts

# -----------------------------------------------------------------------------
# Stage 2: builder — Next.js build (.next/standalone üretir)
# -----------------------------------------------------------------------------
FROM node:22-alpine AS builder

RUN apk add --no-cache libc6-compat
RUN corepack enable && corepack prepare pnpm@11.1.2 --activate

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Telemetri kapalı + production NODE_ENV
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# next.config.ts'te output: "standalone" → minimal runtime
RUN pnpm exec next build

# -----------------------------------------------------------------------------
# Stage 3: runner — Sadece runtime artifact'leri (en küçük katman)
# -----------------------------------------------------------------------------
FROM node:22-alpine AS runner

RUN apk add --no-cache libc6-compat

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Root olmayan kullanıcı — güvenlik en iyi pratiği
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Public assets (favicon, statik resim, vb.)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Standalone server + minimal node_modules (Next.js yalnız ihtiyacı olanı paketler)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# Statik build'ler (CSS, chunk'lar) — standalone'a otomatik dahil değil
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# Health probe (Caddy'nin kontrolüne açık) — basit TCP, opsiyonel HTTP path
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

# Next.js standalone server.js entry point'i builder aşamasında üretir
CMD ["node", "server.js"]
