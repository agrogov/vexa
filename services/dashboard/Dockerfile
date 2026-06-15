# Build stage
FROM docker.ib-ci.com/node:20-alpine AS builder

WORKDIR /app

# Optional build-time basePath (e.g. /vexa)
ARG NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH

# Install dependencies
COPY services/dashboard/package*.json ./
COPY services/dashboard/vexaai-transcript-rendering-0.4.1.tgz ./
RUN npm ci

# Copy source code
COPY services/dashboard/src ./src
COPY services/dashboard/public ./public
COPY services/dashboard/next.config.ts services/dashboard/tsconfig.json services/dashboard/postcss.config.mjs services/dashboard/eslint.config.mjs ./
COPY services/dashboard/components.json ./
COPY services/dashboard/scripts ./scripts
COPY VERSION /VERSION

ARG NEXT_PUBLIC_VEXA_OSS_VERSION
ARG NEXT_PUBLIC_VEXA_OSS_RELEASE_DATE
ARG VEXA_API_URL=http://localhost:8066
ENV NEXT_PUBLIC_VEXA_OSS_VERSION=$NEXT_PUBLIC_VEXA_OSS_VERSION
ENV NEXT_PUBLIC_VEXA_OSS_RELEASE_DATE=$NEXT_PUBLIC_VEXA_OSS_RELEASE_DATE
ENV VEXA_API_URL=$VEXA_API_URL

# Build application
# Note: No NEXT_PUBLIC_* variables needed at build time.
# All client configuration is provided at runtime via /api/config endpoint.
RUN npm run build

# Production stage
FROM docker.ib-ci.com/node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Install CA tools and trust Infobip Root CA
RUN apk add --no-cache ca-certificates curl
RUN curl -fsSL http://ca.infobip.com/crl/RootCA.crt -o /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --chown=nextjs:nodejs services/dashboard/docker-entrypoint.sh ./docker-entrypoint.sh

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

ENTRYPOINT ["./docker-entrypoint.sh"]
