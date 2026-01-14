#!/bin/bash
set -e

# Create multiple databases for different services
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    -- Create databases
    CREATE DATABASE iris_db;
    CREATE DATABASE rag_db;
    CREATE DATABASE nextcloud_db;
    CREATE DATABASE paperless_db;

    -- Grant privileges
    GRANT ALL PRIVILEGES ON DATABASE iris_db TO postgres;
    GRANT ALL PRIVILEGES ON DATABASE rag_db TO postgres;
    GRANT ALL PRIVILEGES ON DATABASE nextcloud_db TO postgres;
    GRANT ALL PRIVILEGES ON DATABASE paperless_db TO postgres;

    \echo 'Databases created successfully'
EOSQL
