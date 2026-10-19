-- Run this file after selecting the database named by DB_NAME.
CREATE TABLE IF NOT EXISTS users (
	user_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
	username VARCHAR(50) NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	role ENUM('ADMIN', 'USER') NOT NULL DEFAULT 'USER',
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (user_id),
	UNIQUE KEY uq_users_username (username),
	UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS polls (
	poll_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
	title VARCHAR(160) NOT NULL,
	description TEXT NOT NULL,
	start_date DATETIME NOT NULL,
	end_date DATETIME NOT NULL,
	created_by INT UNSIGNED NOT NULL,
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (poll_id),
	KEY ix_polls_dates (start_date, end_date),
	CONSTRAINT fk_polls_creator FOREIGN KEY (created_by)
		REFERENCES users (user_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS poll_options (
	option_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
	label VARCHAR(160) NOT NULL,
	poll_id INT UNSIGNED NOT NULL,
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (option_id),
	UNIQUE KEY uq_options_poll_option (poll_id, option_id),
	CONSTRAINT fk_options_poll FOREIGN KEY (poll_id)
		REFERENCES polls (poll_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS votes (
	vote_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
	user_id INT UNSIGNED NOT NULL,
	poll_id INT UNSIGNED NOT NULL,
	option_id INT UNSIGNED NOT NULL,
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (vote_id),
	UNIQUE KEY uq_votes_user_poll (user_id, poll_id),
	KEY ix_votes_poll_option (poll_id, option_id),
	CONSTRAINT fk_votes_user FOREIGN KEY (user_id)
		REFERENCES users (user_id) ON DELETE CASCADE,
	CONSTRAINT fk_votes_poll FOREIGN KEY (poll_id)
		REFERENCES polls (poll_id) ON DELETE CASCADE,
	CONSTRAINT fk_votes_poll_option FOREIGN KEY (poll_id, option_id)
		REFERENCES poll_options (poll_id, option_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
