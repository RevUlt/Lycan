# Lycan Bot

Bot de Discord modular con API REST integrada.

## Requisitos

- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 16

## Instalación

```bash
# Clonar y entrar
cd Lycan

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables
cp .env.example .env
# Editar .env con tus credenciales reales
```

## Configuración (.env)

> ⚠️ **Importante antes de continuar:**
> Los valores marcados con *Por ejemplo* son **completamente inventados** y están ahí solo para que entiendas el formato.
> Por favor, jamás uses esos ejemplos como información real — reemplaza cada campo por algo único, privado y que solo tú conozcas.
> Si alguien más tiene acceso a estos valores, tiene acceso a tu bot.

```env
# Token del bot de Discord — obtenido desde Discord Developer Portal
# Por ejemplo: OTk4NzY1NDMyMTAxNTY3OA.GXz1aB.xK9mQ2vL7nP4wRjT
# → Ese token de arriba es falso. El tuyo es único, no lo compartas con nadie ni lo subas a ningún repositorio.
DISCORD_TOKEN=

# Contraseña de la base de datos PostgreSQL
# Por ejemplo: TrainWhistle!Monte2077
# → Usa algo que solo tú puedas recordar o asociar. Nada de "1234", "password" ni el nombre de tu perro.
DB_PASSWORD=

# URL completa de conexión a PostgreSQL (incluye la contraseña de arriba)
# Por ejemplo: postgresql://lycan:TrainWhistle!Monte2077@localhost:5432/lycan
# → El usuario, contraseña y nombre de DB deben coincidir con lo que configuraste.
DATABASE_URL=

# Puerto donde escucha la API interna (generalmente no necesitas cambiarlo)
API_PORT=7000

# Clave secreta para autenticar la API REST
# Por ejemplo: w8!Kz#2mPqL$vN5xRj
# → No uses esa. Genera la tuya con el comando de abajo — cada instalación debe tener una distinta.
API_SECRET_KEY=

# ID de tu servidor de Discord
# Por ejemplo: 987654321012345678
# → Es solo números. Lo encuentras activando Modo Desarrollador en Discord y haciendo clic derecho en tu servidor.
DISCORD_GUILD_ID=

# Tu ID de usuario en Discord (el dueño del bot)
# Por ejemplo: 123456789098765432
# → Igual que el anterior, clic derecho en tu perfil con Modo Desarrollador activado.
LYCAN_OWNER_ID=

# API Key de OpenRouter (necesaria para el módulo de IA)
# Por ejemplo: sk-or-v1-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
# → La obtienes en openrouter.ai. No la compartas, da acceso a tu cuenta y tiene costos asociados.
OPENROUTER_API_KEY=

# Opcional — dejar vacío si no se usa
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
YOUTUBE_API_KEY=
```

Para generar una clave segura para `API_SECRET_KEY`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Iniciar

```bash
# Levantar PostgreSQL
sudo docker-compose up -d postgres

# Ejecutar bot + API
source venv/bin/activate
python main.py
```

El bot y la API arrancan simultáneamente:
- **Bot**: Se conecta a Discord
- **API**: `http://localhost:7000`

## Módulos

| Módulo | Descripción | Comandos |
|--------|-------------|----------|
| **Welcome** | Bienvenidas/despedidas | `/welcome channel`, `/goodbye message` |
| **Cleaning** | Limpieza de mensajes | `/clean messages`, `/clean user`, `/clean bots` |
| **Hub** | Salas de voz temporales | `/hub setup`, `/hub create` |
| **Embeds** | Creador de embeds | `/embed create`, `/embed send` |
| **Auditor** | Sistema de logs | `/audit channel`, `/audit enable` |
| **Tickets** | Soporte con tickets | `/tickets setup`, `/tickets add_category` |
| **Socials** | Notificaciones Twitch/YT | `/socials add_twitch` |

## API REST

Base: `http://localhost:7000`

### Autenticación
```
X-Api-Key: <tu API_SECRET_KEY>
```

### Endpoints principales

```
GET  /                              # Estado del bot
GET  /guilds                        # Lista de servidores
GET  /guilds/{id}                   # Info de servidor
GET  /guilds/{id}/welcome           # Config de bienvenida
POST /guilds/{id}/welcome/channel   # Configurar canal
POST /guilds/{id}/welcome/test      # Simular bienvenida
POST /guilds/{id}/clean             # Limpiar mensajes
GET  /guilds/{id}/embeds            # Lista embeds
POST /guilds/{id}/embeds            # Crear embed
POST /guilds/{id}/embeds/send       # Enviar embed
GET  /guilds/{id}/audit             # Config auditor
POST /guilds/{id}/audit             # Configurar auditor
GET  /guilds/{id}/tickets           # Lista tickets
POST /guilds/{id}/tickets/categories # Crear categoría
```

Docs interactivas: `http://localhost:7000/docs`

## Estructura

```
Lycan/
├── main.py              # Entry point
├── core/                # Núcleo del bot
│   ├── bot.py          # Clase principal
│   ├── config.py       # Configuración
│   ├── database.py     # Pool PostgreSQL
│   └── logger.py       # Logging
├── modules/             # Módulos del bot
│   ├── welcome/        # Bienvenidas
│   ├── cleaning/       # Limpieza
│   ├── hub/            # Salas temporales
│   ├── embeds/         # Constructor embeds
│   ├── auditor/        # Logs
│   ├── tickets/        # Sistema tickets
│   └── socials/        # Twitch/YouTube
├── api/                 # FastAPI
│   └── server.py       # Endpoints
├── config/
│   └── settings.yaml   # Config general
├── data/migrations/     # SQL migrations
├── docker-compose.yml
└── Dockerfile
```

## Docker (Producción)

```bash
sudo docker-compose up -d
```

## Licencia

MIT
