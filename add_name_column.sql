ALTER TABLE hunt_teammember ADD COLUMN name VARCHAR(100) DEFAULT '';
UPDATE hunt_teammember SET name = role WHERE name IS NULL OR name = '';
