DO $$
BEGIN
    IF to_regclass('public.posts') IS NULL THEN
        RAISE NOTICE 'posts table not ready yet; alembic will create it.';
        RETURN;
    END IF;

    INSERT INTO posts (title, body)
    VALUES ('Hello from SQL seed', 'Inserted via db/seed.sql during first boot.')
    ON CONFLICT DO NOTHING;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'posts table missing; skipping seed insert.';
END $$;
