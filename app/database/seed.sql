-- Demo credentials: admin / AgoraDemo2026!
-- Change this password after importing the sample data.
INSERT INTO users (username, email, password_hash, role)
VALUES (
    'admin',
    'admin@example.com',
    'pbkdf2:sha256:600000$0123456789abcdef0123456789abcdef$8e676da1df8c8616df39e8d4c4dc38498f02e4ebf1fff3a7c0dba63f8b8b2267',
    'ADMIN'
)
ON DUPLICATE KEY UPDATE user_id = LAST_INSERT_ID(user_id);

SET @admin_id = LAST_INSERT_ID();

INSERT INTO polls (title, description, start_date, end_date, created_by)
SELECT 'What should our next community day be?',
       'Help us pick a lovely way to spend time together. Your vote makes the plan!',
       NOW() - INTERVAL 1 HOUR,
       NOW() + INTERVAL 30 DAY,
       @admin_id
WHERE NOT EXISTS (
    SELECT 1 FROM polls WHERE title = 'What should our next community day be?'
);

SET @poll_id = (
    SELECT poll_id FROM polls
    WHERE title = 'What should our next community day be?'
    ORDER BY poll_id LIMIT 1
);

INSERT INTO poll_options (label, poll_id)
SELECT choices.label, @poll_id
FROM (
    SELECT 'A picnic in the park' AS label
    UNION ALL SELECT 'A cozy movie night'
    UNION ALL SELECT 'A creative craft afternoon'
) AS choices
WHERE NOT EXISTS (
    SELECT 1 FROM poll_options WHERE poll_id = @poll_id AND label = choices.label
);
