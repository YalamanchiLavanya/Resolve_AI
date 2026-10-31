DROP DATABASE IF EXISTS resolveai;
CREATE DATABASE resolveai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE resolveai;
-- =====================================================================
-- 1. TABLES
-- =====================================================================
-- ---------- Roles & Users (RBAC) ----------
CREATE TABLE roles (
    role_id     TINYINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    role_name   ENUM('CUSTOMER','SUPPORT_AGENT','TEAM_LEAD','ADMIN') NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE users (
    user_id       INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    role_id       TINYINT UNSIGNED NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,          -- store bcrypt hash only
    phone         VARCHAR(20),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    last_login    DATETIME NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(role_id),
    INDEX idx_users_role (role_id)
);

-- ---------- Teams ----------
CREATE TABLE teams (
    team_id      INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    team_name    VARCHAR(80) NOT NULL UNIQUE,
    description  VARCHAR(255),
    team_lead_id INT UNSIGNED NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_teams_lead FOREIGN KEY (team_lead_id) REFERENCES users(user_id)
);

CREATE TABLE team_members (
    team_id   INT UNSIGNED NOT NULL,
    user_id   INT UNSIGNED NOT NULL,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_id, user_id),
    CONSTRAINT fk_tm_team FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    CONSTRAINT fk_tm_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ---------- Plans & Customer Profiles ----------
CREATE TABLE plans (
    plan_id       INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    plan_name     VARCHAR(60) NOT NULL UNIQUE,
    speed_mbps    INT UNSIGNED NOT NULL,
    monthly_price DECIMAL(8,2) NOT NULL,
    data_limit_gb INT UNSIGNED NULL,  
    is_premium    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE customer_profiles (
    customer_id       INT UNSIGNED PRIMARY KEY,     -- same as users.user_id
    plan_id           INT UNSIGNED NOT NULL,
    account_number    VARCHAR(20) NOT NULL UNIQUE,
    address           VARCHAR(255) NOT NULL,
    city              VARCHAR(60),
    pincode           CHAR(6) NOT NULL,
    connection_type   ENUM('FIBER','WIRELESS','CABLE') NOT NULL DEFAULT 'FIBER',
    connection_id     VARCHAR(30) NOT NULL UNIQUE,  -- e.g. FTTH-AP-000123
    router_model      VARCHAR(60),
    ip_address        VARCHAR(45),
    installation_date DATE,
    connection_status ENUM('ACTIVE','SUSPENDED','DISCONNECTED') NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_cp_user FOREIGN KEY (customer_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_cp_plan FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    INDEX idx_cp_pincode (pincode)
);

-- ---------- Categories & SLA ----------
CREATE TABLE categories (
    category_id      INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    category_name    VARCHAR(60) NOT NULL UNIQUE,
    description      VARCHAR(255),
    default_team_id  INT UNSIGNED NULL,
    default_priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
    CONSTRAINT fk_cat_team FOREIGN KEY (default_team_id) REFERENCES teams(team_id)
);

CREATE TABLE sla_policies (
    sla_id                 INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    priority               ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL UNIQUE,
    first_response_minutes INT UNSIGNED NOT NULL,
    resolution_minutes     INT UNSIGNED NOT NULL
);

-- ---------- Outages (Bonus: outage detection by pin code) ----------
CREATE TABLE outages (
    outage_id        INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    title            VARCHAR(150) NOT NULL,
    pincode          CHAR(6) NOT NULL,
    area_name        VARCHAR(100),
    description      TEXT,
    status           ENUM('DETECTED','CONFIRMED','RESOLVED') NOT NULL DEFAULT 'DETECTED',
    detected_by      ENUM('AI','AGENT','ADMIN') NOT NULL DEFAULT 'AI',
    detected_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at      DATETIME NULL,
    affected_tickets INT UNSIGNED NOT NULL DEFAULT 0,
    INDEX idx_outage_pin (pincode, status)
);

-- ---------- Tickets ----------
CREATE TABLE tickets (
    ticket_id            INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_number        VARCHAR(20) UNIQUE,                       -- TKT-000001 (set by trigger)
    customer_id          INT UNSIGNED NOT NULL,
    category_id          INT UNSIGNED NULL,
    subject              VARCHAR(200) NOT NULL,
    description          TEXT NOT NULL,
    channel              ENUM('EMAIL','APP','PHONE','WEB') NOT NULL DEFAULT 'WEB',
    priority             ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
    status               ENUM('OPEN','ASSIGNED','IN_PROGRESS','PENDING_CUSTOMER','RESOLVED','CLOSED') NOT NULL DEFAULT 'OPEN',
    assigned_agent_id    INT UNSIGNED NULL,
    team_id              INT UNSIGNED NULL,
    sla_id               INT UNSIGNED NULL,
    first_response_due   DATETIME NULL,
    resolution_due       DATETIME NULL,
    first_responded_at   DATETIME NULL,
    resolved_at          DATETIME NULL,
    closed_at            DATETIME NULL,
    sla_breached         BOOLEAN NOT NULL DEFAULT FALSE,
    is_escalated         BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_level     TINYINT UNSIGNED NOT NULL DEFAULT 0,
    -- AI fields
    ai_category_id       INT UNSIGNED NULL,
    ai_confidence        DECIMAL(5,2) NULL,                        -- 0-100
    sentiment            ENUM('POSITIVE','NEUTRAL','NEGATIVE','ANGRY') NULL,
    sentiment_score      DECIMAL(4,3) NULL,                        -- -1.000 to 1.000
    is_at_risk           BOOLEAN NOT NULL DEFAULT FALSE,           -- angry / churn-risk customer
    repeat_contact_count INT UNSIGNED NOT NULL DEFAULT 0,
    outage_id            INT UNSIGNED NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_t_customer FOREIGN KEY (customer_id)       REFERENCES users(user_id),
    CONSTRAINT fk_t_category FOREIGN KEY (category_id)       REFERENCES categories(category_id),
    CONSTRAINT fk_t_agent    FOREIGN KEY (assigned_agent_id) REFERENCES users(user_id),
    CONSTRAINT fk_t_team     FOREIGN KEY (team_id)           REFERENCES teams(team_id),
    CONSTRAINT fk_t_sla      FOREIGN KEY (sla_id)            REFERENCES sla_policies(sla_id),
    CONSTRAINT fk_t_aicat    FOREIGN KEY (ai_category_id)    REFERENCES categories(category_id),
    CONSTRAINT fk_t_outage   FOREIGN KEY (outage_id)         REFERENCES outages(outage_id),
    INDEX idx_t_status   (status),
    INDEX idx_t_priority (priority),
    INDEX idx_t_agent    (assigned_agent_id),
    INDEX idx_t_team     (team_id),
    INDEX idx_t_customer (customer_id),
    INDEX idx_t_due      (resolution_due),
    INDEX idx_t_created  (created_at)
);

CREATE TABLE ticket_attachments (
    attachment_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_id     INT UNSIGNED NOT NULL,
    uploaded_by   INT UNSIGNED NOT NULL,
    file_name     VARCHAR(255) NOT NULL,
    file_path     VARCHAR(500) NOT NULL,
    file_type     VARCHAR(50),
    file_size_kb  INT UNSIGNED,
    uploaded_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_att_ticket FOREIGN KEY (ticket_id)   REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    CONSTRAINT fk_att_user   FOREIGN KEY (uploaded_by) REFERENCES users(user_id)
);

-- Public replies AND internal notes (is_internal = TRUE => hidden from customer)
CREATE TABLE ticket_comments (
    comment_id      INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_id       INT UNSIGNED NOT NULL,
    author_id       INT UNSIGNED NOT NULL,
    body            TEXT NOT NULL,
    is_internal     BOOLEAN NOT NULL DEFAULT FALSE,
    is_ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tc_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    CONSTRAINT fk_tc_author FOREIGN KEY (author_id) REFERENCES users(user_id),
    INDEX idx_tc_ticket (ticket_id)
);

-- Ticket history (audit of status/assignment changes)
CREATE TABLE ticket_history (
    history_id   INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_id    INT UNSIGNED NOT NULL,
    changed_by   INT UNSIGNED NULL,
    field_name   VARCHAR(40) NOT NULL,
    old_value    VARCHAR(100),
    new_value    VARCHAR(100),
    changed_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_th_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    INDEX idx_th_ticket (ticket_id)
);

CREATE TABLE ticket_escalations (
    escalation_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_id     INT UNSIGNED NOT NULL,
    level         TINYINT UNSIGNED NOT NULL DEFAULT 1,
    reason        ENUM('SLA_BREACH','SLA_WARNING','ANGRY_CUSTOMER','REPEAT_CONTACT','MANUAL','OUTAGE') NOT NULL,
    escalated_to  INT UNSIGNED NULL,          -- team lead / admin
    escalated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes         VARCHAR(255),
    CONSTRAINT fk_te_ticket FOREIGN KEY (ticket_id)    REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    CONSTRAINT fk_te_to     FOREIGN KEY (escalated_to) REFERENCES users(user_id)
);

-- ---------- Knowledge Base ----------
CREATE TABLE kb_articles (
    article_id    INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    category_id   INT UNSIGNED NULL,
    title         VARCHAR(200) NOT NULL,
    problem       TEXT,
    solution      TEXT NOT NULL,
    tags          VARCHAR(255),
    author_id     INT UNSIGNED NOT NULL,
    is_published  BOOLEAN NOT NULL DEFAULT TRUE,
    view_count    INT UNSIGNED NOT NULL DEFAULT 0,
    helpful_count INT UNSIGNED NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_kb_cat    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    CONSTRAINT fk_kb_author FOREIGN KEY (author_id)   REFERENCES users(user_id),
    FULLTEXT INDEX ft_kb (title, problem, solution, tags)
);

-- ---------- AI Suggestions log (Categorise / Route / Reply / Sentiment / Outage) ----------
CREATE TABLE ai_suggestions (
    suggestion_id   INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_id       INT UNSIGNED NOT NULL,
    suggestion_type ENUM('CATEGORY','PRIORITY','ROUTING','REPLY','SENTIMENT','OUTAGE','KB_MATCH') NOT NULL,
    suggested_value TEXT,
    kb_article_id   INT UNSIGNED NULL,
    model_used      VARCHAR(60),                 -- e.g. 'scikit-learn-tfidf-lr', 'gemini-1.5-flash'
    confidence      DECIMAL(5,2) NULL,
    was_accepted    BOOLEAN NULL,                -- NULL = not reviewed yet
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_ticket FOREIGN KEY (ticket_id)     REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_kb     FOREIGN KEY (kb_article_id) REFERENCES kb_articles(article_id),
    INDEX idx_ai_ticket (ticket_id)
);

-- ---------- Customer Satisfaction ----------
CREATE TABLE ticket_ratings (
    rating_id   INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ticket_id   INT UNSIGNED NOT NULL UNIQUE,    -- one rating per ticket
    customer_id INT UNSIGNED NOT NULL,
    rating      TINYINT UNSIGNED NOT NULL,
    feedback    VARCHAR(500),
    rated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_tr_ticket   FOREIGN KEY (ticket_id)   REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    CONSTRAINT fk_tr_customer FOREIGN KEY (customer_id) REFERENCES users(user_id)
);

-- ---------- Notifications, Audit, Weekly CSAT report ----------
CREATE TABLE notifications (
    notification_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id         INT UNSIGNED NOT NULL,
    ticket_id       INT UNSIGNED NULL,
    message         VARCHAR(255) NOT NULL,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_n_user   FOREIGN KEY (user_id)   REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_n_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE SET NULL,
    INDEX idx_n_user (user_id, is_read)
);

CREATE TABLE audit_logs (
    log_id     BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id    INT UNSIGNED NULL,
    action     VARCHAR(60) NOT NULL,        -- LOGIN, LOGIN_FAILED, CREATE_TICKET, ...
    details    VARCHAR(500),
    ip_address VARCHAR(45),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_time (created_at)
);

CREATE TABLE weekly_csat_reports (
    report_id        INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    week_start       DATE NOT NULL,
    week_end         DATE NOT NULL,
    total_tickets    INT UNSIGNED NOT NULL,
    resolved_tickets INT UNSIGNED NOT NULL,
    avg_rating       DECIMAL(3,2),
    sla_compliance   DECIMAL(5,2),
    generated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_week (week_start)
);

-- =====================================================================
-- 2. TRIGGERS
-- =====================================================================
DELIMITER $$

-- 2.1 On ticket creation: set SLA, due times, ticket number placeholder
CREATE TRIGGER trg_tickets_before_insert
BEFORE INSERT ON tickets
FOR EACH ROW
BEGIN
    DECLARE v_sla_id INT UNSIGNED;
    DECLARE v_first  INT UNSIGNED;
    DECLARE v_res    INT UNSIGNED;

    SELECT sla_id, first_response_minutes, resolution_minutes
      INTO v_sla_id, v_first, v_res
      FROM sla_policies WHERE priority = NEW.priority LIMIT 1;

    SET NEW.sla_id             = v_sla_id;
    SET NEW.first_response_due = DATE_ADD(IFNULL(NEW.created_at, NOW()), INTERVAL v_first MINUTE);
    SET NEW.resolution_due     = DATE_ADD(IFNULL(NEW.created_at, NOW()), INTERVAL v_res MINUTE);
    SET NEW.ticket_number      = CONCAT('TMP-', UUID_SHORT()); -- replaced with TKT-000001 format after insert

    -- Angry customers are automatically flagged at-risk
    IF NEW.sentiment = 'ANGRY' THEN
        SET NEW.is_at_risk = TRUE;
    END IF;
END$$

-- 2.2 After insert: replace placeholder with clean sequential number
CREATE TRIGGER trg_tickets_after_insert
AFTER INSERT ON tickets
FOR EACH ROW
BEGIN
    INSERT INTO ticket_history (ticket_id, changed_by, field_name, old_value, new_value)
    VALUES (NEW.ticket_id, NEW.customer_id, 'STATUS', NULL, NEW.status);
END$$

-- 2.3 On update: maintain timestamps, SLA flag, re-compute SLA when priority changes
CREATE TRIGGER trg_tickets_before_update
BEFORE UPDATE ON tickets
FOR EACH ROW
BEGIN
    DECLARE v_first INT UNSIGNED;
    DECLARE v_res   INT UNSIGNED;
    DECLARE v_sla   INT UNSIGNED;

    -- status -> resolved / closed timestamps
    IF NEW.status = 'RESOLVED' AND OLD.status <> 'RESOLVED' THEN
        SET NEW.resolved_at = NOW();
        IF NEW.resolution_due IS NOT NULL AND NOW() > NEW.resolution_due THEN
            SET NEW.sla_breached = TRUE;
        END IF;
    END IF;
    IF NEW.status = 'CLOSED' AND OLD.status <> 'CLOSED' THEN
        SET NEW.closed_at = NOW();
    END IF;

    -- auto-move to ASSIGNED when an agent is set on an OPEN ticket
    IF NEW.assigned_agent_id IS NOT NULL AND OLD.assigned_agent_id IS NULL AND NEW.status = 'OPEN' THEN
        SET NEW.status = 'ASSIGNED';
    END IF;

    -- priority changed -> recalculate SLA from creation time
    IF NEW.priority <> OLD.priority THEN
        SELECT sla_id, first_response_minutes, resolution_minutes
          INTO v_sla, v_first, v_res
          FROM sla_policies WHERE priority = NEW.priority LIMIT 1;
        SET NEW.sla_id             = v_sla;
        SET NEW.first_response_due = DATE_ADD(OLD.created_at, INTERVAL v_first MINUTE);
        SET NEW.resolution_due     = DATE_ADD(OLD.created_at, INTERVAL v_res MINUTE);
    END IF;
END$$

-- 2.4 After update: write history rows
CREATE TRIGGER trg_tickets_after_update
AFTER UPDATE ON tickets
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status THEN
        INSERT INTO ticket_history (ticket_id, field_name, old_value, new_value)
        VALUES (NEW.ticket_id, 'STATUS', OLD.status, NEW.status);
    END IF;
    IF NOT (NEW.assigned_agent_id <=> OLD.assigned_agent_id) THEN
        INSERT INTO ticket_history (ticket_id, field_name, old_value, new_value)
        VALUES (NEW.ticket_id, 'ASSIGNED_AGENT', OLD.assigned_agent_id, NEW.assigned_agent_id);
    END IF;
    IF NEW.priority <> OLD.priority THEN
        INSERT INTO ticket_history (ticket_id, field_name, old_value, new_value)
        VALUES (NEW.ticket_id, 'PRIORITY', OLD.priority, NEW.priority);
    END IF;
END$$

-- 2.5 First public agent reply records first_responded_at
CREATE TRIGGER trg_comment_after_insert
AFTER INSERT ON ticket_comments
FOR EACH ROW
BEGIN
    DECLARE v_role VARCHAR(20);
    SELECT r.role_name INTO v_role
      FROM users u JOIN roles r ON r.role_id = u.role_id
     WHERE u.user_id = NEW.author_id;

    IF NEW.is_internal = FALSE AND v_role IN ('SUPPORT_AGENT','TEAM_LEAD','ADMIN') THEN
        UPDATE tickets
           SET first_responded_at = NOW()
         WHERE ticket_id = NEW.ticket_id AND first_responded_at IS NULL;
    END IF;
END$$

DELIMITER ;

-- =====================================================================
-- 3. STORED PROCEDURES & EVENT
-- =====================================================================
DELIMITER $$

-- 3.1 Final ticket number format TKT-000001 (call after creating a ticket)
CREATE PROCEDURE sp_create_ticket(
    IN  p_customer_id INT UNSIGNED,
    IN  p_subject     VARCHAR(200),
    IN  p_description TEXT,
    IN  p_category_id INT UNSIGNED,
    IN  p_priority    VARCHAR(10),
    IN  p_channel     VARCHAR(10),
    OUT p_ticket_id   INT UNSIGNED
)
BEGIN
    DECLARE v_team INT UNSIGNED;
    DECLARE v_repeat INT UNSIGNED;

    SELECT default_team_id INTO v_team FROM categories WHERE category_id = p_category_id;

    -- repeat contacts in last 7 days
    SELECT COUNT(*) INTO v_repeat FROM tickets
     WHERE customer_id = p_customer_id AND created_at >= NOW() - INTERVAL 7 DAY;

    INSERT INTO tickets (customer_id, category_id, subject, description, channel,
                         priority, team_id, repeat_contact_count)
    VALUES (p_customer_id, p_category_id, p_subject, p_description, p_channel,
            p_priority, v_team, v_repeat);

    SET p_ticket_id = LAST_INSERT_ID();
    UPDATE tickets SET ticket_number = CONCAT('TKT-', LPAD(p_ticket_id, 6, '0'))
     WHERE ticket_id = p_ticket_id;
END$$

-- 3.2 Auto-assign to the agent in the ticket's team with the fewest open tickets
CREATE PROCEDURE sp_auto_assign(IN p_ticket_id INT UNSIGNED)
BEGIN
    DECLARE v_team  INT UNSIGNED;
    DECLARE v_agent INT UNSIGNED;

    SELECT team_id INTO v_team FROM tickets WHERE ticket_id = p_ticket_id;

    SELECT u.user_id INTO v_agent
      FROM team_members tm
      JOIN users u ON u.user_id = tm.user_id AND u.is_active = TRUE
      JOIN roles r ON r.role_id = u.role_id AND r.role_name = 'SUPPORT_AGENT'
      LEFT JOIN tickets t ON t.assigned_agent_id = u.user_id
                         AND t.status IN ('ASSIGNED','IN_PROGRESS','PENDING_CUSTOMER')
     WHERE tm.team_id = v_team
     GROUP BY u.user_id
     ORDER BY COUNT(t.ticket_id) ASC
     LIMIT 1;

    IF v_agent IS NOT NULL THEN
        UPDATE tickets SET assigned_agent_id = v_agent WHERE ticket_id = p_ticket_id;
    END IF;
END$$

-- 3.3 SLA monitoring: mark breaches and escalate (also run by the scheduled event)
CREATE PROCEDURE sp_check_sla_breaches()
BEGIN
    -- Escalate tickets that just breached
    INSERT INTO ticket_escalations (ticket_id, level, reason, escalated_to, notes)
    SELECT t.ticket_id, 1, 'SLA_BREACH', tm.team_lead_id, 'Auto-escalated: resolution SLA breached'
      FROM tickets t
      LEFT JOIN teams tm ON tm.team_id = t.team_id
     WHERE t.status NOT IN ('RESOLVED','CLOSED')
       AND t.resolution_due < NOW()
       AND t.sla_breached = FALSE;

    UPDATE tickets
       SET sla_breached = TRUE, is_escalated = TRUE,
           escalation_level = GREATEST(escalation_level, 1)
     WHERE status NOT IN ('RESOLVED','CLOSED')
       AND resolution_due < NOW()
       AND sla_breached = FALSE;

    -- Warn team leads of tickets within 20 minutes of breaching
    INSERT INTO notifications (user_id, ticket_id, message)
    SELECT tm.team_lead_id, t.ticket_id,
           CONCAT('SLA warning: ', t.ticket_number, ' breaches in < 20 min')
      FROM tickets t JOIN teams tm ON tm.team_id = t.team_id
     WHERE t.status NOT IN ('RESOLVED','CLOSED')
       AND t.sla_breached = FALSE
       AND t.resolution_due BETWEEN NOW() AND NOW() + INTERVAL 20 MINUTE
       AND tm.team_lead_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM notifications n
                        WHERE n.ticket_id = t.ticket_id AND n.message LIKE 'SLA warning%');
END$$

-- 3.4 Outage pattern detection: >= p_threshold open tickets from one pincode in last 30 min
CREATE PROCEDURE sp_detect_outages(IN p_threshold INT)
BEGIN
    DECLARE v_pin CHAR(6);
    DECLARE v_cnt INT;
    DECLARE v_outage INT UNSIGNED;
    DECLARE done INT DEFAULT 0;

    DECLARE cur CURSOR FOR
        SELECT cp.pincode, COUNT(*) AS c
          FROM tickets t
          JOIN customer_profiles cp ON cp.customer_id = t.customer_id
          JOIN categories c ON c.category_id = t.category_id
         WHERE t.created_at >= NOW() - INTERVAL 30 MINUTE
           AND t.status NOT IN ('RESOLVED','CLOSED')
           AND c.category_name IN ('Internet Down / Outage','Slow Speed')
         GROUP BY cp.pincode
        HAVING COUNT(*) >= p_threshold;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_pin, v_cnt;
        IF done = 1 THEN LEAVE read_loop; END IF;

        -- MAX() returns NULL when no matching outage exists; it does not
        -- trigger the cursor's NOT FOUND handler.
        SELECT MAX(outage_id) INTO v_outage
          FROM outages
         WHERE pincode = v_pin AND status <> 'RESOLVED';

        IF v_outage IS NULL THEN
            INSERT INTO outages (title, pincode, description, detected_by, affected_tickets)
            VALUES (CONCAT('Suspected outage in ', v_pin), v_pin,
                    CONCAT(v_cnt, ' similar tickets in the last 30 minutes'), 'AI', v_cnt);
            SET v_outage = LAST_INSERT_ID();
        ELSE
            UPDATE outages SET affected_tickets = v_cnt WHERE outage_id = v_outage;
        END IF;

        -- link tickets to the outage
        UPDATE tickets t
          JOIN customer_profiles cp ON cp.customer_id = t.customer_id
           SET t.outage_id = v_outage
         WHERE cp.pincode = v_pin
           AND t.created_at >= NOW() - INTERVAL 30 MINUTE
           AND t.status NOT IN ('RESOLVED','CLOSED');

        SET v_outage = NULL;
    END LOOP;
    CLOSE cur;
END$$

-- 3.5 Weekly customer satisfaction report
CREATE PROCEDURE sp_generate_weekly_csat(IN p_week_start DATE)
BEGIN
    DECLARE v_end DATE;
    SET v_end = DATE_ADD(p_week_start, INTERVAL 6 DAY);

    REPLACE INTO weekly_csat_reports
        (week_start, week_end, total_tickets, resolved_tickets, avg_rating, sla_compliance)
    SELECT p_week_start, v_end,
           COUNT(*),
           SUM(t.status IN ('RESOLVED','CLOSED')),
           (SELECT ROUND(AVG(r.rating),2) FROM ticket_ratings r
             WHERE DATE(r.rated_at) BETWEEN p_week_start AND v_end),
           ROUND(100 * SUM(t.sla_breached = FALSE) / NULLIF(COUNT(*),0), 2)
      FROM tickets t
     WHERE DATE(t.created_at) BETWEEN p_week_start AND v_end;
END$$

DELIMITER ;

-- Scheduled jobs (needs event scheduler ON; may need admin privileges)
-- Optional: run this separately with an account that has the required privilege.
-- SET GLOBAL event_scheduler = ON;

CREATE EVENT ev_sla_monitor
ON SCHEDULE EVERY 5 MINUTE
DO CALL sp_check_sla_breaches();

CREATE EVENT ev_outage_monitor
ON SCHEDULE EVERY 10 MINUTE
DO CALL sp_detect_outages(5);

-- =====================================================================
-- 4. VIEWS (dashboards)
-- =====================================================================
CREATE VIEW v_ticket_details AS
SELECT t.ticket_id, t.ticket_number, t.subject, t.status, t.priority, t.channel,
       c.category_name, cu.full_name AS customer_name, cp.plan_id, p.plan_name,
       cp.connection_id, cp.pincode,
       ag.full_name AS agent_name, tm.team_name,
       t.sentiment, t.is_at_risk, t.is_escalated, t.sla_breached,
       t.first_response_due, t.resolution_due, t.created_at, t.resolved_at
  FROM tickets t
  JOIN users cu ON cu.user_id = t.customer_id
  LEFT JOIN customer_profiles cp ON cp.customer_id = t.customer_id
  LEFT JOIN plans p ON p.plan_id = cp.plan_id
  LEFT JOIN categories c ON c.category_id = t.category_id
  LEFT JOIN users ag ON ag.user_id = t.assigned_agent_id
  LEFT JOIN teams tm ON tm.team_id = t.team_id;

CREATE VIEW v_agent_performance AS
SELECT u.user_id AS agent_id, u.full_name,
       COUNT(t.ticket_id)                                         AS total_assigned,
       SUM(t.status IN ('RESOLVED','CLOSED'))                     AS resolved,
       SUM(t.sla_breached)                                        AS sla_breaches,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, t.created_at, t.resolved_at)),1) AS avg_resolution_min,
       ROUND(AVG(r.rating),2)                                     AS avg_rating
  FROM users u
  JOIN roles ro ON ro.role_id = u.role_id AND ro.role_name = 'SUPPORT_AGENT'
  LEFT JOIN tickets t ON t.assigned_agent_id = u.user_id
  LEFT JOIN ticket_ratings r ON r.ticket_id = t.ticket_id
 GROUP BY u.user_id, u.full_name;

CREATE VIEW v_queue_summary AS
SELECT tm.team_name,
       SUM(t.status = 'OPEN')                              AS open_unassigned,
       SUM(t.status IN ('ASSIGNED','IN_PROGRESS'))         AS in_progress,
       SUM(t.status = 'PENDING_CUSTOMER')                  AS pending_customer,
       SUM(t.sla_breached)                                 AS breached,
       SUM(t.is_at_risk)                                   AS at_risk
  FROM teams tm
  LEFT JOIN tickets t ON t.team_id = tm.team_id AND t.status NOT IN ('RESOLVED','CLOSED')
 GROUP BY tm.team_name;

CREATE VIEW v_sla_metrics AS
SELECT priority,
       COUNT(*)                                   AS total,
       SUM(sla_breached)                          AS breached,
       ROUND(100 * (1 - SUM(sla_breached)/COUNT(*)), 2) AS compliance_pct
  FROM tickets
 GROUP BY priority;

CREATE VIEW v_category_stats AS
SELECT c.category_name, COUNT(t.ticket_id) AS total_tickets,
       ROUND(AVG(t.ai_confidence),1) AS avg_ai_confidence
  FROM categories c LEFT JOIN tickets t ON t.category_id = c.category_id
 GROUP BY c.category_name;

CREATE VIEW v_active_outages AS
SELECT o.outage_id, o.title, o.pincode, o.status, o.detected_at,
       COUNT(t.ticket_id) AS linked_tickets
  FROM outages o LEFT JOIN tickets t ON t.outage_id = o.outage_id
 WHERE o.status <> 'RESOLVED'
 GROUP BY o.outage_id, o.title, o.pincode, o.status, o.detected_at;

-- =====================================================================
-- 5. SYNTHETIC SEED DATA
-- NOTE: password_hash values below are dummy bcrypt-style placeholders.
--       Generate real hashes in the backend (passlib/bcrypt) for login.
-- =====================================================================
INSERT INTO roles (role_name, description) VALUES
 ('CUSTOMER','Raises tickets, tracks status, rates resolution'),
 ('SUPPORT_AGENT','Handles assigned tickets with AI-suggested replies'),
 ('TEAM_LEAD','Monitors queues, SLAs and agent performance'),
 ('ADMIN','Manages teams, categories, SLAs and knowledge base');

INSERT INTO sla_policies (priority, first_response_minutes, resolution_minutes) VALUES
 ('CRITICAL', 15,   240),
 ('HIGH',     30,   480),
 ('MEDIUM',   120,  1440),
 ('LOW',      240,  4320);

INSERT INTO plans (plan_name, speed_mbps, monthly_price, data_limit_gb, is_premium) VALUES
 ('Basic 50',    50,  499.00, 500,  FALSE),
 ('Standard 100',100, 749.00, 1000, FALSE),
 ('Premium 300', 300, 1199.00, NULL, TRUE),
 ('Ultra 1Gbps', 1000,1999.00, NULL, TRUE);

-- Users (1 admin, 2 leads, 4 agents, 6 customers)
INSERT INTO users (role_id, full_name, email, password_hash, phone) VALUES
 (4,'Anita Admin',     'admin@resolveai.test',  '$2b$12$dummyhashADMIN000000000000000000000000000000000000000', '9000000001'),
 (3,'Rahul Lead',      'lead.billing@resolveai.test', '$2b$12$dummyhashLEAD1000000000000000000000000000000000000000','9000000002'),
 (3,'Sneha Lead',      'lead.tech@resolveai.test',    '$2b$12$dummyhashLEAD2000000000000000000000000000000000000000','9000000003'),
 (2,'Kiran Agent',     'kiran@resolveai.test',  '$2b$12$dummyhashAGENT100000000000000000000000000000000000000','9000000004'),
 (2,'Meena Agent',     'meena@resolveai.test',  '$2b$12$dummyhashAGENT200000000000000000000000000000000000000','9000000005'),
 (2,'Arjun Agent',     'arjun@resolveai.test',  '$2b$12$dummyhashAGENT300000000000000000000000000000000000000','9000000006'),
 (2,'Divya Agent',     'divya@resolveai.test',  '$2b$12$dummyhashAGENT400000000000000000000000000000000000000','9000000007'),
 (1,'Ravi Kumar',      'ravi@customer.test',    '$2b$12$dummyhashCUST1000000000000000000000000000000000000000','9100000001'),
 (1,'Lakshmi Devi',    'lakshmi@customer.test', '$2b$12$dummyhashCUST2000000000000000000000000000000000000000','9100000002'),
 (1,'Suresh Babu',     'suresh@customer.test',  '$2b$12$dummyhashCUST3000000000000000000000000000000000000000','9100000003'),
 (1,'Priya Sharma',    'priya@customer.test',   '$2b$12$dummyhashCUST4000000000000000000000000000000000000000','9100000004'),
 (1,'Vikram Reddy',    'vikram@customer.test',  '$2b$12$dummyhashCUST5000000000000000000000000000000000000000','9100000005'),
 (1,'Fatima Khan',     'fatima@customer.test',  '$2b$12$dummyhashCUST6000000000000000000000000000000000000000','9100000006');
-- user_ids: 1 admin | 2,3 leads | 4-7 agents | 8-13 customers

INSERT INTO teams (team_name, description, team_lead_id) VALUES
 ('Billing & Accounts','Billing queries, refunds, plan changes', 2),
 ('Technical Support', 'Speed, router, connection issues',       3),
 ('Network Operations','Outages and infrastructure faults',      3),
 ('General Support',   'Installation and other queries',         2);

INSERT INTO team_members (team_id, user_id) VALUES
 (1,2),(1,4),(1,5),
 (2,3),(2,6),(2,7),
 (3,3),(3,7),
 (4,2),(4,4),(4,5);

INSERT INTO categories (category_name, description, default_team_id, default_priority) VALUES
 ('Billing Issue',          'Wrong charges, invoices, refunds',         1, 'MEDIUM'),
 ('Slow Speed',             'Speeds lower than plan',                   2, 'MEDIUM'),
 ('Internet Down / Outage', 'No connectivity',                          3, 'HIGH'),
 ('Router / Device',        'Router, ONT, Wi-Fi hardware problems',     2, 'MEDIUM'),
 ('Plan Change / Upgrade',  'Upgrade, downgrade, renewal',              1, 'LOW'),
 ('New Installation',       'New connection, shifting',                 4, 'LOW'),
 ('Complaint / Escalation', 'Repeat complaints, service dissatisfaction',4,'HIGH');

INSERT INTO customer_profiles
 (customer_id, plan_id, account_number, address, city, pincode, connection_type, connection_id, router_model, ip_address, installation_date)
VALUES
 (8, 2,'ACC100001','12-4 Gandhi Nagar',   'Vijayawada','520010','FIBER','FTTH-AP-000101','TP-Link AX23','10.20.1.11','2024-02-10'),
 (9, 1,'ACC100002','5-8 Main Road',       'Vijayawada','520010','FIBER','FTTH-AP-000102','Huawei HG8145','10.20.1.12','2023-11-05'),
 (10,3,'ACC100003','44 Benz Circle',      'Vijayawada','520010','FIBER','FTTH-AP-000103','Netgear R6700','10.20.1.13','2025-01-20'),
 (11,4,'ACC100004','9 Labbipet',          'Vijayawada','520010','FIBER','FTTH-AP-000104','Asus RT-AX88U','10.20.1.14','2025-06-15'),
 (12,2,'ACC100005','21 Ring Road',        'Guntur',    '522001','WIRELESS','WRL-AP-000201','Tenda F3','10.30.2.21','2024-08-01'),
 (13,1,'ACC100006','3 Brodipet',          'Guntur',    '522002','CABLE','CBL-AP-000301','D-Link DIR-825','10.30.3.31','2022-12-12');

INSERT INTO kb_articles (category_id, title, problem, solution, tags, author_id) VALUES
 (2,'Fix slow internet speed',
    'Customer reports speeds lower than plan.',
    '1) Restart router and ONT. 2) Test on a wired device. 3) Check for background downloads. 4) Switch to 5 GHz band. 5) If speed < 70% of plan after steps, raise a line-quality check.',
    'slow,speed,wifi,router', 1),
 (3,'No internet - LOS red light',
    'Router shows red LOS light and no connectivity.',
    'Check fiber cable for bends/cuts, reseat the connector. If LOS remains red, check area outage status by pincode; if none, dispatch a field technician.',
    'down,outage,los,red light,fiber', 1),
 (1,'Duplicate charge refund',
    'Customer charged twice for the same billing cycle.',
    'Verify in billing system, raise refund request with transaction ID. Refunds take 5-7 working days to reflect.',
    'billing,refund,duplicate,charge', 1),
 (4,'Wi-Fi keeps disconnecting',
    'Wi-Fi drops frequently.',
    'Change Wi-Fi channel, update router firmware, move router to a central location, factory reset as last resort.',
    'wifi,disconnect,router', 1),
 (5,'How to upgrade your plan',
    'Customer wants a higher speed plan.',
    'Upgrade is possible from app or support. New plan activates within 24 hours; billing is pro-rated.',
    'upgrade,plan,speed', 1),
 (6,'Shifting connection to new address',
    'Customer is relocating.',
    'Raise shifting request 5 days ahead. Technician visit is scheduled after address verification.',
    'shifting,relocate,install', 1);

-- Outage (for pincode 520010 cluster)
INSERT INTO outages (title, pincode, area_name, description, status, detected_by, detected_at, affected_tickets)
VALUES ('Fiber cut near Benz Circle','520010','Benz Circle, Vijayawada',
        'Multiple customers reporting LOS in the area','CONFIRMED','AI', NOW() - INTERVAL 40 MINUTE, 3);

-- Tickets (SLA dates auto-set by trigger)
INSERT INTO tickets
 (customer_id, category_id, subject, description, channel, priority, status, team_id, assigned_agent_id,
  sentiment, sentiment_score, ai_category_id, ai_confidence, outage_id, created_at)
VALUES
 (8, 3,'Internet not working since morning','Red light on router, no internet since 7 AM. Third time this month!','PHONE','HIGH','ASSIGNED',3,7,'ANGRY',-0.850,3,94.20,1, NOW() - INTERVAL 35 MINUTE),
 (9, 3,'No connection','LOS light is red. Please help.','APP','HIGH','OPEN',3,NULL,'NEGATIVE',-0.400,3,91.00,1, NOW() - INTERVAL 30 MINUTE),
 (10,2,'Very slow speed on premium plan','Paying for 300 Mbps but getting only 20 Mbps.','EMAIL','MEDIUM','IN_PROGRESS',2,6,'NEGATIVE',-0.550,2,88.50,NULL, NOW() - INTERVAL 5 HOUR),
 (11,1,'Charged twice this month','I see two debits of Rs.1999 for October. Please refund.','WEB','MEDIUM','IN_PROGRESS',1,4,'NEUTRAL',-0.100,1,96.00,NULL, NOW() - INTERVAL 1 DAY),
 (12,5,'Upgrade to 300 Mbps','Want to upgrade my plan from 100 to 300 Mbps.','APP','LOW','RESOLVED',1,5,'POSITIVE',0.600,5,97.30,NULL, NOW() - INTERVAL 2 DAY),
 (13,4,'Wi-Fi keeps disconnecting','Wi-Fi drops every 10 minutes on all devices.','WEB','MEDIUM','PENDING_CUSTOMER',2,7,'NEUTRAL',-0.200,4,90.10,NULL, NOW() - INTERVAL 3 HOUR),
 (8, 7,'Repeated complaints not resolved','I have complained 3 times, nobody fixes it. I want to cancel my connection.','PHONE','CRITICAL','OPEN',4,NULL,'ANGRY',-0.950,7,89.00,NULL, NOW() - INTERVAL 10 MINUTE);

-- Fix ticket numbers to TKT-000001 format
UPDATE tickets
   SET ticket_number = CONCAT('TKT-', LPAD(ticket_id, 6, '0'))
 WHERE ticket_id > 0;

INSERT INTO ticket_comments (ticket_id, author_id, body, is_internal, is_ai_generated) VALUES
 (1, 7,'Hi Ravi, sorry for the trouble. We detected a fiber issue in your area and our team is working on it. ETA 2 hours.',FALSE,TRUE),
 (1, 7,'Customer is angry, 3rd complaint. Linked to Benz Circle outage #1. Offer goodwill credit.',TRUE,FALSE),
 (3, 6,'Please run a wired speed test and share the result.',FALSE,FALSE),
 (4, 4,'Duplicate payment confirmed. Refund initiated, reference RF-77821.',TRUE,FALSE),
 (4, 4,'Hi Vikram, we have confirmed the duplicate charge and initiated a refund. It should reflect in 5-7 working days.',FALSE,TRUE),
 (5, 5,'Your plan has been upgraded to 300 Mbps. It will be active within 24 hours.',FALSE,FALSE);

UPDATE tickets SET status = 'RESOLVED' WHERE ticket_id = 5;

INSERT INTO ai_suggestions (ticket_id, suggestion_type, suggested_value, kb_article_id, model_used, confidence, was_accepted) VALUES
 (1,'CATEGORY','Internet Down / Outage',NULL,'scikit-learn-tfidf-lr',94.20,TRUE),
 (1,'SENTIMENT','ANGRY (-0.85)',NULL,'gemini-1.5-flash',92.00,TRUE),
 (1,'OUTAGE','Possible outage in pincode 520010',NULL,'rule-based-cluster',88.00,TRUE),
 (3,'KB_MATCH','Fix slow internet speed',1,'tfidf-cosine',81.50,TRUE),
 (4,'REPLY','Hi Vikram, we have confirmed the duplicate charge...',3,'gemini-1.5-flash',90.00,TRUE),
 (7,'PRIORITY','CRITICAL - churn risk',NULL,'gemini-1.5-flash',89.00,NULL);

INSERT INTO ticket_ratings (ticket_id, customer_id, rating, feedback) VALUES
 (5, 12, 5, 'Quick and polite service!');

INSERT INTO ticket_escalations (ticket_id, level, reason, escalated_to, notes) VALUES
 (7, 1, 'ANGRY_CUSTOMER', 2, 'Customer threatening to disconnect; repeat complaints');
UPDATE tickets SET is_escalated = TRUE, escalation_level = 1, is_at_risk = TRUE WHERE ticket_id = 7;

INSERT INTO notifications (user_id, ticket_id, message) VALUES
 (2, 7, 'At-risk customer escalated: TKT-000007'),
 (3, 1, 'Outage cluster detected in 520010');

INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES
 (1,'LOGIN','Admin login','127.0.0.1'),
 (8,'CREATE_TICKET','TKT-000001 created','127.0.0.1');

-- =====================================================================
-- 6. USEFUL QUERIES FOR YOUR BACKEND / DEMO
-- =====================================================================
-- Admin / Team lead dashboard
-- SELECT * FROM v_queue_summary;
-- SELECT * FROM v_sla_metrics;
-- SELECT * FROM v_agent_performance;
-- SELECT * FROM v_active_outages;
-- SELECT * FROM v_category_stats;

-- Customer: my tickets (never show internal notes to customers)
-- SELECT * FROM v_ticket_details WHERE customer_name = 'Ravi Kumar';
-- SELECT * FROM ticket_comments WHERE ticket_id = 1 AND is_internal = FALSE;

-- Agent: my open queue ordered by urgency
-- SELECT * FROM v_ticket_details
--  WHERE agent_name = 'Kiran Agent' AND status NOT IN ('RESOLVED','CLOSED')
--  ORDER BY FIELD(priority,'CRITICAL','HIGH','MEDIUM','LOW'), resolution_due;

-- Customer 360 view for the agent (plan + connection + history)
-- SELECT u.full_name, p.plan_name, cp.connection_id, cp.pincode, cp.router_model, t.ticket_number, t.subject, t.status
--   FROM users u JOIN customer_profiles cp ON cp.customer_id = u.user_id
--   JOIN plans p ON p.plan_id = cp.plan_id
--   LEFT JOIN tickets t ON t.customer_id = u.user_id
--  WHERE u.user_id = 8;

-- KB search used by the AI "similar solutions" feature
-- SELECT article_id, title, MATCH(title,problem,solution,tags) AGAINST ('slow speed wifi' IN NATURAL LANGUAGE MODE) AS score
--   FROM kb_articles ORDER BY score DESC LIMIT 3;

-- Run manually to test automation
-- CALL sp_check_sla_breaches();
-- CALL sp_detect_outages(3);
-- CALL sp_generate_weekly_csat(DATE_SUB(CURDATE(), INTERVAL 6 DAY));
-- CALL sp_auto_assign(2);

SELECT 'ResolveAI database created successfully' AS status;
USE resolveai;
SHOW TABLES;
SELECT * FROM tickets;
SELECT * FROM v_ticket_details;
SELECT * FROM v_agent_performance;
SELECT * FROM v_queue_summary;