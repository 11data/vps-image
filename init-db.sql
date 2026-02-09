-- Mission Control Database Initialization
-- This script is automatically run by PostgreSQL on container startup

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Mission Control tables
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'backlog',
    priority INTEGER DEFAULT 0,
    agent_id VARCHAR(100),
    assigned_to VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS activity_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    source VARCHAR(100),
    data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    config JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_events_type ON activity_events(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_events_created ON activity_events(created_at DESC);

-- Insert default task categories/backlog items
INSERT INTO tasks (title, description, status, priority) VALUES
    ('Welcome to Mission Control', 'Getting started with your AI agent workspace', 'backlog', 1),
    ('Review your agent configuration', 'Check that your agent is properly configured', 'backlog', 2)
ON CONFLICT DO NOTHING;
