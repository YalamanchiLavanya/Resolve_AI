USE resolveai;

UPDATE tickets
SET ticket_number = CONCAT(
    'TKT-',
    LPAD(ticket_id, 6, '0')
)
WHERE ticket_id > 0;

SELECT
    ticket_id,
    ticket_number,
    subject,
    status
FROM tickets
ORDER BY ticket_id;

USE resolveai;

SHOW TABLES;

SELECT * FROM v_ticket_details;

SELECT * FROM v_agent_performance;

SELECT * FROM v_queue_summary;

SELECT * FROM v_sla_metrics;

SELECT * FROM v_active_outages;
USE resolveai;
SHOW TABLES;
SELECT
    ticket_id,
    ticket_number,
    subject,
    status
FROM resolveai.tickets
ORDER BY ticket_id;
SELECT
    ticket_id,
    ticket_number,
    subject,
    status
FROM resolveai.tickets
ORDER BY ticket_id;
DESCRIBE resolveai.tickets;