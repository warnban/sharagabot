from sqlite3 import IntegrityError

from bot.db import execute, fetchall, fetchone, now_iso, transaction


async def list_subjects(internal_chat_id: int) -> list:
    rows = await fetchall(
        "SELECT * FROM subjects WHERE chat_id = ?",
        (internal_chat_id,),
    )
    return sorted(rows, key=lambda row: row["name"].casefold())


async def get_subject(subject_id: int, internal_chat_id: int):
    return await fetchone(
        "SELECT * FROM subjects WHERE id = ? AND chat_id = ?",
        (subject_id, internal_chat_id),
    )


async def find_subject(internal_chat_id: int, name: str):
    # SQLite NOCASE does not casefold Cyrillic, so compare here.
    target = " ".join(name.split())
    folded = target.casefold()
    rows = await list_subjects(internal_chat_id)
    for row in rows:
        if row["name"] == target:
            return row
    for row in rows:
        if row["name"].casefold() == folded:
            return row
    return None


async def create_subject(
    internal_chat_id: int,
    name: str,
    internal_user_id: int,
) -> str:
    if await find_subject(internal_chat_id, name) is not None:
        return "exists"
    try:
        async with transaction():
            await execute(
                """
                INSERT INTO subjects (chat_id, name, created_by, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (internal_chat_id, name, internal_user_id, now_iso()),
            )
    except IntegrityError:
        return "exists"
    return "ok"


async def delete_subject(subject_id: int, internal_chat_id: int) -> bool:
    async with transaction():
        await execute(
            """
            DELETE FROM attachments
            WHERE record_id IN (
                SELECT id FROM records
                WHERE subject_id = ? AND chat_id = ?
            )
            """,
            (subject_id, internal_chat_id),
        )
        await execute(
            "DELETE FROM records WHERE subject_id = ? AND chat_id = ?",
            (subject_id, internal_chat_id),
        )
        cursor = await execute(
            "DELETE FROM subjects WHERE id = ? AND chat_id = ?",
            (subject_id, internal_chat_id),
        )
        deleted = cursor.rowcount > 0
    return deleted
