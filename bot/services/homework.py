from bot.db import execute, fetchall, fetchone, now_iso, transaction
from bot.texts import KIND_HW, KIND_NOTE


async def count_records(subject_id: int, kind: str | None) -> int:
    if kind is None:
        row = await fetchone(
            "SELECT COUNT(*) AS total FROM records WHERE subject_id = ?",
            (subject_id,),
        )
    else:
        row = await fetchone(
            "SELECT COUNT(*) AS total FROM records WHERE subject_id = ? AND kind = ?",
            (subject_id, kind),
        )
    if row is None:
        return 0
    return int(row["total"])


async def list_records(
    subject_id: int,
    kind: str | None,
    *,
    limit: int,
    offset: int,
) -> list:
    if kind is None:
        return await fetchall(
            """
            SELECT id, subject_id, kind, date, text
            FROM records
            WHERE subject_id = ?
            ORDER BY date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (subject_id, limit, offset),
        )
    return await fetchall(
        """
        SELECT id, subject_id, kind, date, text
        FROM records
        WHERE subject_id = ? AND kind = ?
        ORDER BY date DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (subject_id, kind, limit, offset),
    )


async def get_record(record_id: int, internal_chat_id: int):
    return await fetchone(
        """
        SELECT
            r.id,
            r.chat_id,
            r.subject_id,
            r.kind,
            r.date,
            r.text,
            r.created_by,
            r.created_at,
            r.updated_at,
            s.name AS subject_name,
            u.username AS author_username,
            u.telegram_id AS author_telegram_id,
            (
                SELECT COUNT(*)
                FROM attachments AS a
                WHERE a.record_id = r.id AND a.file_type = 'photo'
            ) AS photo_count,
            (
                SELECT COUNT(*)
                FROM attachments AS a
                WHERE a.record_id = r.id AND a.file_type = 'document'
            ) AS doc_count
        FROM records AS r
        JOIN subjects AS s ON s.id = r.subject_id
        LEFT JOIN users AS u ON u.id = r.created_by
        WHERE r.id = ? AND r.chat_id = ?
        """,
        (record_id, internal_chat_id),
    )


async def create_record(
    *,
    internal_chat_id: int,
    subject_id: int,
    kind: str,
    date_iso: str,
    text: str,
    internal_user_id: int,
    attachments: list[dict],
) -> int | None:
    if kind not in {KIND_HW, KIND_NOTE}:
        return None
    subject = await fetchone(
        "SELECT id FROM subjects WHERE id = ? AND chat_id = ?",
        (subject_id, internal_chat_id),
    )
    if subject is None:
        return None
    created = now_iso()
    async with transaction():
        cursor = await execute(
            """
            INSERT INTO records (
                chat_id, subject_id, kind, date, text, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                internal_chat_id,
                subject_id,
                kind,
                date_iso,
                text,
                internal_user_id,
                created,
                created,
            ),
        )
        record_id = cursor.lastrowid
        for item in attachments:
            await execute(
                """
                INSERT INTO attachments (
                    record_id, file_id, file_type, file_name, caption, uploaded_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    item["file_id"],
                    item["file_type"],
                    item.get("file_name"),
                    item.get("caption"),
                    internal_user_id,
                    created,
                ),
            )
    return record_id


async def update_text(record_id: int, internal_chat_id: int, text: str) -> bool:
    cursor = await execute(
        """
        UPDATE records
        SET text = ?, updated_at = ?
        WHERE id = ? AND chat_id = ?
        """,
        (text, now_iso(), record_id, internal_chat_id),
    )
    return cursor.rowcount > 0


async def delete_record(record_id: int, internal_chat_id: int) -> bool:
    async with transaction():
        await execute(
            """
            DELETE FROM attachments
            WHERE record_id IN (
                SELECT id FROM records WHERE id = ? AND chat_id = ?
            )
            """,
            (record_id, internal_chat_id),
        )
        cursor = await execute(
            "DELETE FROM records WHERE id = ? AND chat_id = ?",
            (record_id, internal_chat_id),
        )
        deleted = cursor.rowcount > 0
    return deleted
