-- Initial database schema for drama generation system
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Dramas table
CREATE TABLE IF NOT EXISTS dramas (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    premise TEXT NOT NULL,
    url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1 -- For optimistic locking
);

CREATE INDEX idx_dramas_created_at ON dramas(created_at DESC);
CREATE INDEX idx_dramas_updated_at ON dramas(updated_at DESC);

-- Characters table
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    drama_id TEXT NOT NULL REFERENCES dramas(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    gender TEXT NOT NULL,
    voice_description TEXT NOT NULL,
    main BOOLEAN DEFAULT FALSE,
    url TEXT,
    premise_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_characters_drama_id ON characters(drama_id);
CREATE INDEX idx_characters_main ON characters(main) WHERE main = TRUE;

-- Episodes table
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    drama_id TEXT NOT NULL REFERENCES dramas(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    premise TEXT,
    url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_episodes_drama_id ON episodes(drama_id);

-- Scenes table
CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    drama_id TEXT NOT NULL REFERENCES dramas(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    image_url TEXT,
    video_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scenes_episode_id ON scenes(episode_id);
CREATE INDEX idx_scenes_drama_id ON scenes(drama_id);

-- Assets table (polymorphic - can belong to drama, character, episode, or scene)
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    drama_id TEXT NOT NULL REFERENCES dramas(id) ON DELETE CASCADE,

    -- Polymorphic ownership (exactly one should be set)
    character_id TEXT REFERENCES characters(id) ON DELETE CASCADE,
    episode_id TEXT REFERENCES episodes(id) ON DELETE CASCADE,
    scene_id TEXT REFERENCES scenes(id) ON DELETE CASCADE,

    kind TEXT NOT NULL CHECK (kind IN ('image', 'video')),
    depends_on JSONB DEFAULT '[]', -- Array of asset/character IDs
    prompt TEXT NOT NULL,
    duration INTEGER, -- Seconds for video assets
    url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure exactly one parent is set
    CONSTRAINT asset_has_one_parent CHECK (
        (character_id IS NOT NULL)::int +
        (episode_id IS NOT NULL)::int +
        (scene_id IS NOT NULL)::int +
        ((character_id IS NULL AND episode_id IS NULL AND scene_id IS NULL))::int = 1
    )
);

CREATE INDEX idx_assets_drama_id ON assets(drama_id);
CREATE INDEX idx_assets_character_id ON assets(character_id);
CREATE INDEX idx_assets_episode_id ON assets(episode_id);
CREATE INDEX idx_assets_scene_id ON assets(scene_id);
CREATE INDEX idx_assets_kind ON assets(kind);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    parent_job_id TEXT REFERENCES jobs(job_id) ON DELETE CASCADE,
    drama_id TEXT NOT NULL REFERENCES dramas(id) ON DELETE CASCADE,
    asset_id TEXT, -- Not a FK since it can be various types
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    prompt TEXT,
    depends_on JSONB DEFAULT '[]', -- Array of asset IDs
    reference_paths JSONB DEFAULT '[]', -- Array of file paths
    result_path TEXT,
    r2_url TEXT,
    r2_key TEXT,
    asset_metadata JSONB,
    metadata JSONB DEFAULT '{}',

    -- For parent jobs (drama-level)
    title TEXT,
    user_id TEXT,
    project_name TEXT,
    child_jobs JSONB DEFAULT '[]', -- Array of child job IDs
    total_jobs INTEGER DEFAULT 0,
    completed_jobs INTEGER DEFAULT 0,
    failed_jobs INTEGER DEFAULT 0,
    running_jobs INTEGER DEFAULT 0,
    pending_jobs INTEGER DEFAULT 0,

    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Index for quick lookups
    CONSTRAINT valid_job_type CHECK (job_type IN ('drama', 'image', 'video', 'filmstrip', 'generate_drama', 'improve_drama', 'critique_drama', 'generate_image', 'generate_video', 'generate_audio'))
);

CREATE INDEX idx_jobs_drama_id ON jobs(drama_id);
CREATE INDEX idx_jobs_parent_job_id ON jobs(parent_job_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_asset_id ON jobs(asset_id);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to all tables
CREATE TRIGGER update_dramas_updated_at BEFORE UPDATE ON dramas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_characters_updated_at BEFORE UPDATE ON characters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_episodes_updated_at BEFORE UPDATE ON episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scenes_updated_at BEFORE UPDATE ON scenes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assets_updated_at BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-increment version on drama updates (for optimistic locking)
CREATE OR REPLACE FUNCTION increment_drama_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER increment_drama_version_trigger BEFORE UPDATE ON dramas
    FOR EACH ROW EXECUTE FUNCTION increment_drama_version();

-- Enable Row Level Security (optional, but recommended)
ALTER TABLE dramas ENABLE ROW LEVEL SECURITY;
ALTER TABLE characters ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenes ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations (adjust based on your auth requirements)
-- For development, we'll allow all operations
CREATE POLICY "Allow all on dramas" ON dramas FOR ALL USING (true);
CREATE POLICY "Allow all on characters" ON characters FOR ALL USING (true);
CREATE POLICY "Allow all on episodes" ON episodes FOR ALL USING (true);
CREATE POLICY "Allow all on scenes" ON scenes FOR ALL USING (true);
CREATE POLICY "Allow all on assets" ON assets FOR ALL USING (true);
CREATE POLICY "Allow all on jobs" ON jobs FOR ALL USING (true);
