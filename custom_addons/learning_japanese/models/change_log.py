import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PURGED_CURSOR_PARAM = "learning_japanese.change_log_purged_through"
RETENTION_DAYS = 90

# An event is readable once its transaction can no longer add rows before it:
# every transaction older than the snapshot's xmin has finished. The current
# transaction may read its own rows (only happens inside tests).
VISIBLE_SQL = (
    "(txid < pg_snapshot_xmin(pg_current_snapshot())"
    " OR txid = pg_current_xact_id_if_assigned())"
)


def parse_cursor(value):
    """'<txid>-<seq>' (or '0') -> (txid, seq); raise ValueError when malformed."""
    value = (value or "0").strip()
    if value == "0":
        return 0, 0
    txid, sep, seq = value.partition("-")
    if not sep or not txid.isdigit() or not seq.isdigit():
        raise ValueError(value)
    return int(txid), int(seq)


def format_cursor(txid, seq):
    return f"{txid}-{seq}" if txid else "0"


class ChangeLog(models.Model):
    """Outbox of the change feed (GET /api/lj/v1/changes).

    Rows are written with plain SQL in the same transaction as the ORM change,
    so a rolled back change never produces an event. The table is created by
    hand to get a bigserial id and the inserting transaction id (xid8), which
    the feed cursor is ordered by.
    """

    _name = "learning_japanese.change_log"
    _description = "Change Feed Event"
    _table = "lj_change_log"
    _auto = False
    _order = "id desc"
    _rec_name = "entity"

    entity = fields.Char(readonly=True)
    res_id = fields.Integer(string="Record ID", readonly=True)
    op = fields.Selection(
        selection=[("create", "Create"), ("update", "Update"), ("delete", "Delete")],
        readonly=True,
    )
    at = fields.Datetime(readonly=True)
    user_id = fields.Many2one("res.users", string="User", readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS lj_change_log (
                id bigserial PRIMARY KEY,
                entity varchar NOT NULL,
                res_id integer NOT NULL,
                op varchar NOT NULL,
                at timestamp without time zone NOT NULL DEFAULT (now() at time zone 'UTC'),
                user_id integer,
                txid xid8 NOT NULL DEFAULT pg_current_xact_id()
            );
            CREATE INDEX IF NOT EXISTS lj_change_log_cursor_idx ON lj_change_log (txid, id);
            CREATE INDEX IF NOT EXISTS lj_change_log_at_idx ON lj_change_log (at);
        """)

    @api.model
    def _record(self, entity, ids, op):
        """Append one event per id. Duplicates are harmless: consumers refetch."""
        ids = sorted({int(i) for i in ids if i})
        if not ids:
            return
        self.env.cr.execute(
            """
            INSERT INTO lj_change_log (entity, res_id, op, user_id)
            SELECT %s, unnest(%s::int[]), %s, %s
            """,
            [entity, ids, op, self.env.uid],
        )

    @api.model
    def _head_cursor(self):
        """Cursor of the newest readable event (never older than the purge mark)."""
        self.env.cr.execute(f"""
            SELECT txid::text, id FROM lj_change_log
            WHERE {VISIBLE_SQL}
            ORDER BY txid DESC, id DESC
            LIMIT 1
        """)
        row = self.env.cr.fetchone()
        head = (int(row[0]), row[1]) if row else (0, 0)
        return format_cursor(*max(head, self._purged_through()))

    @api.model
    def _purged_through(self):
        value = self.env["ir.config_parameter"].sudo().get_param(PURGED_CURSOR_PARAM)
        try:
            return parse_cursor(value)
        except ValueError:
            return 0, 0

    @api.model
    def _read_after(self, after, limit):
        """Return (events, next_after, has_more) for events strictly after `after`.

        Raises ValueError for a malformed cursor and LookupError when events
        after it were already purged.
        """
        txid, seq = parse_cursor(after)
        purged = self._purged_through()
        if purged > (0, 0) and (txid, seq) < purged:
            raise LookupError(after)
        self.env.cr.execute(
            f"""
            SELECT id, txid::text, entity, res_id, op, at
            FROM lj_change_log
            WHERE {VISIBLE_SQL} AND (txid, id) > (%s::xid8, %s)
            ORDER BY txid, id
            LIMIT %s
            """,
            [str(txid), seq, limit + 1],
        )
        rows = self.env.cr.fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        events = [
            {"seq": row[0], "entity": row[2], "id": row[3], "op": row[4], "at": row[5]}
            for row in rows
        ]
        next_after = format_cursor(int(rows[-1][1]), rows[-1][0]) if rows else format_cursor(txid, seq)
        return events, next_after, has_more

    @api.model
    def _cron_purge(self, days=RETENTION_DAYS):
        """Delete events older than `days` and remember how far the log was cut."""
        cutoff = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            """
            SELECT txid::text, id FROM lj_change_log
            WHERE at < %s ORDER BY txid DESC, id DESC LIMIT 1
            """,
            [cutoff],
        )
        row = self.env.cr.fetchone()
        if not row:
            return
        mark = max((int(row[0]), row[1]), self._purged_through())
        self.env.cr.execute("DELETE FROM lj_change_log WHERE at < %s", [cutoff])
        _logger.info("Purged %s change log events older than %s", self.env.cr.rowcount, cutoff)
        self.env["ir.config_parameter"].sudo().set_param(PURGED_CURSOR_PARAM, format_cursor(*mark))
