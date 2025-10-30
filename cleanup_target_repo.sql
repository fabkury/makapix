-- Clean up incorrect target_repo values
-- This updates all target_repo values that are GitHub Pages URLs (ending with .github.io)
-- to NULL, since they should be repository names, not GitHub Pages URLs

UPDATE github_installations 
SET target_repo = NULL 
WHERE target_repo LIKE '%.github.io';

-- Verify the cleanup
SELECT id, user_id, installation_id, account_login, target_repo 
FROM github_installations 
WHERE target_repo LIKE '%.github.io';

