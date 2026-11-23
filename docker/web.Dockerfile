# Frontend image (Vite dev server). Only the web app and its shared types are installed.
FROM node:22-bookworm-slim
RUN corepack enable && corepack prepare pnpm@10.28.0 --activate
ENV CI=true
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/shared/package.json packages/shared/
COPY apps/web/package.json apps/web/
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile --filter @kit/web...
COPY packages/shared packages/shared
COPY apps/web apps/web
EXPOSE 5173
CMD ["pnpm", "--filter", "@kit/web", "dev"]
