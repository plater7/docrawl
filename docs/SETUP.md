# Cloudflare Tunnel + Workers VPC Setup

Exposer Docrawl a internet de forma segura sin IP pública, usando Cloudflare Tunnel + Workers VPC.

## Arquitectura

```
[Internet] → [Worker] → (VPC binding) → [Tunnel] → [cloudflared] → [docrawl:8002]
```

- **cloudflared** corre como sidecar en docker-compose y crea una conexión saliente al tunnel
- **No hay Public Hostname** — la app es completamente privada
- Un **VPC Service** vincula el tunnel con el Worker
- El **Worker** es el único punto de entrada público

## Prerequisitos

- Cuenta Cloudflare con Zero Trust habilitado
- `npx wrangler` disponible (`npm install -g wrangler` o usar npx)
- Docker Compose corriendo con Docrawl

---

## Paso 1 — Crear el Tunnel

1. Ve al dashboard de Cloudflare → **Zero Trust** → **Networks** → **Tunnels**
2. Click **Create a tunnel** → selecciona **Cloudflared**
3. Nombre el tunnel: `docrawl` (o el que prefieras)
4. Copia el token que aparece — lo necesitarás en el siguiente paso
5. **No configures un Public Hostname** — el tunnel será privado (acceso solo via Worker)

## Paso 2 — Configurar el token del tunnel

Copia `.env.example` a `.env` (si no lo hiciste ya) y agrega el token:

```bash
cp .env.example .env
```

Edita `.env`:

```env
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiM...  # token del dashboard
```

## Paso 3 — Crear el VPC Service

1. En el dashboard de Cloudflare → **Zero Trust** → **Networks** → **VPC Services**
2. Click **Create VPC Service**
3. Selecciona el tunnel `docrawl` que creaste
4. Copia el **Service ID** (formato UUID: `019c53c3-e7ab-7ca1-b454-93cdb207dbd4`)

## Paso 4 — Configurar el Worker

Edita `worker/wrangler.jsonc` con el Service ID copiado:

```jsonc
{
  "name": "docrawl-worker",
  "main": "src/index.js",
  "compatibility_date": "2025-01-28",
  "vpc_services": [
    {
      "binding": "VPC_SERVICE",
      "service_id": "TU-SERVICE-ID-AQUI",
      "remote": true
    }
  ]
}
```

## Paso 5 — Deployar el Worker

```bash
cd worker
npm install
npx wrangler deploy
```

El Worker quedará disponible en `https://docrawl-worker.<tu-subdominio>.workers.dev`

## Paso 6 — Levantar Docrawl con cloudflared

```bash
docker compose up --build
```

El sidecar `cloudflared` se conecta automáticamente usando el `CLOUDFLARE_TUNNEL_TOKEN` del `.env`.

---

## Verificación

1. Abre la URL del Worker en el browser
2. Deberías ver la UI de Docrawl
3. Comprueba los logs de cloudflared: `docker compose logs cloudflared`

## Seguridad

Por defecto el Worker **no tiene autenticación**. Para restringir acceso:

- Agrega Cloudflare Access en el Worker (requiere Zero Trust)
- O agrega un header secreto en el Worker y valídalo en FastAPI

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `cloudflared` no conecta | Verifica que `CLOUDFLARE_TUNNEL_TOKEN` esté en `.env` |
| Worker devuelve 502 | El tunnel no está activo — verifica `docker compose logs cloudflared` |
| Worker devuelve 404 | El VPC Service ID no coincide con el tunnel |
| SSE events se cortan | Cloudflare Workers tienen límite de 30s de idle — considera usar `cf-no-cache` header |

---

> 🤖 AI-assisted documentation with human review.
