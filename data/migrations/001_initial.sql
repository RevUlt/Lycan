-- Lycan Bot - Schema Inicial
-- v0.1.0

-- Configuración por servidor
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id BIGINT PRIMARY KEY,
    welcome_channel_id BIGINT,
    welcome_message TEXT,
    goodbye_channel_id BIGINT,
    goodbye_message TEXT,
    hub_category_id BIGINT,
    hub_channel_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Salas temporales activas (Hub)
CREATE TABLE IF NOT EXISTS temp_channels (
    channel_id BIGINT PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    is_locked BOOLEAN DEFAULT FALSE,
    allowed_users BIGINT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Feeds de redes sociales
CREATE TABLE IF NOT EXISTS social_feeds (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    platform VARCHAR(20) NOT NULL,
    channel_id VARCHAR(100) NOT NULL,
    discord_channel_id BIGINT NOT NULL,
    last_notified_at TIMESTAMP,
    custom_message TEXT,
    UNIQUE(guild_id, platform, channel_id)
);

-- Templates de embeds
CREATE TABLE IF NOT EXISTS embed_templates (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    embed_data JSONB NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

-- Categorías de tickets (personalizables)
CREATE TABLE IF NOT EXISTS ticket_categories (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    emoji VARCHAR(10),
    UNIQUE(guild_id, name)
);

-- Tickets de soporte
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    claimed_by BIGINT,
    category_id INT REFERENCES ticket_categories(id),
    priority VARCHAR(10) DEFAULT 'normal',
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

-- Configuración de logs (Auditor)
CREATE TABLE IF NOT EXISTS audit_config (
    guild_id BIGINT PRIMARY KEY,
    log_channel_id BIGINT,
    enabled_events TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Logs de limpieza
CREATE TABLE IF NOT EXISTS cleaning_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    messages_deleted INT NOT NULL,
    filter_type VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP
);
