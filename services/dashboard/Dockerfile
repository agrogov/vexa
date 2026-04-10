# Build stage
FROM docker.ib-ci.com/node:20-alpine AS builder

WORKDIR /app

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apk add --no-cache ca-certificates wget \
    && wget -O /usr/local/share/ca-certificates/infobip-rootca.crt http://ca.infobip.com/crl/RootCA.crt \
    && update-ca-certificates
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

# Copy transcript-rendering built package
COPY packages/transcript-rendering/package.json /transcript-rendering/package.json
COPY packages/transcript-rendering/dist/ /transcript-rendering/dist/

# Install dependencies
# Patch package.json to use local transcript-rendering path
COPY services/dashboard/package*.json ./
RUN sed -i 's|file:../../../packages/transcript-rendering|file:/transcript-rendering|' package.json
RUN npm install --ignore-scripts
# Ensure transcript-rendering is physically copied (not symlinked)
RUN rm -rf node_modules/@vexaai/transcript-rendering && \
    cp -r /transcript-rendering node_modules/@vexaai/transcript-rendering

# Copy source code
COPY services/dashboard/src ./src
COPY services/dashboard/public ./public
COPY services/dashboard/next.config.ts services/dashboard/tsconfig.json services/dashboard/postcss.config.mjs services/dashboard/eslint.config.mjs ./
COPY services/dashboard/components.json ./

# Base path for sub-path deployment (e.g. /vexa)
ARG NEXT_PUBLIC_BASE_PATH=""
ENV NEXT_PUBLIC_BASE_PATH=${NEXT_PUBLIC_BASE_PATH}

# Build application
RUN npm run build

# Production stage
FROM docker.ib-ci.com/node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apk add --no-cache ca-certificates wget \
    && wget -O /usr/local/share/ca-certificates/infobip-rootca.crt http://ca.infobip.com/crl/RootCA.crt \
    && update-ca-certificates
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --chown=nextjs:nodejs services/dashboard/docker-entrypoint.sh ./docker-entrypoint.sh

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["./docker-entrypoint.sh"]
