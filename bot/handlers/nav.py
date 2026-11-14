from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import can_edit, is_admin
from bot.handlers import NotCommand
from bot.handlers.homework import (
    AddRecord,
    DATE_STATES,
    _go_text,
    _show_pick_subjects,
    _show_preview,
    begin_add,
    show_card,
    show_records,
    show_sections,
    show_subjects,
)
from bot.handlers.start import send_about
from bot.handlers.subjects import begin_subject_prompt, show_subject_names
from bot import nav, texts
from bot.services import attachments as files
from bot.services import homework as records
from bot.services import subjects as subjects_db

router = Router(name="nav")


class NavPress(NotCommand):
    async def __call__(self, message: Message, state: FSMContext):
        if not await super().__call__(message):
            return False
        text = (message.text or "").strip()
        if text == texts.BTN_HOME:
            return {"nav_action": {"a": "home", "t": text}}
        if text == texts.BTN_ABOUT:
            return {"nav_action": {"a": "about", "t": text}}
        data = await state.get_data()
        for button in data.get("nav") or []:
            if button.get("t") == text:
                return {"nav_action": button}
        return False


def _num(action: dict, key: str, default: int = 0) -> int:
    value = action.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@router.message(NavPress())
async def on_nav(
    message: Message,
    state: FSMContext,
    nav_action: dict,
    role: str | None,
    db_user,
    internal_chat_id: int | None,
) -> None:
    if message.from_user is None or internal_chat_id is None or db_user is None:
        await message.answer(texts.PRIVATE)
        return
    action = nav_action.get("a")
    bot = message.bot
    chat_id = message.chat.id
    reply_to = message.message_id
    user_id = message.from_user.id

    if action == "about":
        await send_about(bot, chat_id)
        return
    if action in {"home", "cancel"}:
        await nav.show_home(bot, chat_id, state, role, reply_to)
        return
    if action == "records":
        await show_subjects(
            bot, chat_id, internal_chat_id, 0, None, role, state, reply_to
        )
        return
    if action == "subjects_page":
        await show_subjects(
            bot, chat_id, internal_chat_id, _num(nav_action, "p"), None, role, state, reply_to
        )
        return
    if action == "add":
        if not can_edit(role):
            await message.answer(texts.NO_ACCESS)
            return
        await begin_add(
            bot,
            chat_id,
            user_id,
            internal_chat_id,
            db_user["id"],
            state,
            role=role,
            reply_to=reply_to,
        )
        return
    if action == "subjects":
        await show_subject_names(
            bot, chat_id, internal_chat_id, None, role, state, reply_to
        )
        return
    if action == "new_subject":
        if not is_admin(role):
            await message.answer(texts.NO_ACCESS)
            return
        await begin_subject_prompt(
            bot,
            chat_id,
            user_id,
            internal_chat_id,
            db_user["id"],
            state,
            reply_to=reply_to,
        )
        return
    if action == "subject":
        await show_sections(
            bot,
            chat_id,
            internal_chat_id,
            _num(nav_action, "id"),
            _num(nav_action, "p"),
            None,
            state,
            reply_to,
        )
        return
    if action == "section":
        await show_records(
            bot,
            chat_id,
            internal_chat_id,
            _num(nav_action, "s"),
            str(nav_action.get("k") or ""),
            -1,
            _num(nav_action, "sp"),
            None,
            state,
            reply_to,
        )
        return
    if action == "records_page":
        await show_records(
            bot,
            chat_id,
            internal_chat_id,
            _num(nav_action, "s"),
            str(nav_action.get("k") or ""),
            _num(nav_action, "p"),
            _num(nav_action, "sp"),
            None,
            state,
            reply_to,
        )
        return
    if action == "record":
        await show_card(
            bot,
            chat_id,
            internal_chat_id,
            _num(nav_action, "id"),
            role,
            state,
            kind=str(nav_action.get("k") or texts.KIND_HW),
            page=_num(nav_action, "p", -1),
            subject_page=_num(nav_action, "sp"),
            reply_to=reply_to,
        )
        return
    if action == "back":
        target = nav_action.get("to")
        if target == "sub":
            await show_subjects(
                bot, chat_id, internal_chat_id, _num(nav_action, "p"), None, role, state, reply_to
            )
            return
        if target == "sec":
            await show_sections(
                bot,
                chat_id,
                internal_chat_id,
                _num(nav_action, "s"),
                _num(nav_action, "sp"),
                None,
                state,
                reply_to,
            )
            return
        if target == "rec":
            await show_records(
                bot,
                chat_id,
                internal_chat_id,
                _num(nav_action, "s"),
                str(nav_action.get("k") or texts.KIND_HW),
                _num(nav_action, "p", -1),
                _num(nav_action, "sp"),
                None,
                state,
                reply_to,
            )
            return
        await show_card(
            bot,
            chat_id,
            internal_chat_id,
            _num(nav_action, "r"),
            role,
            state,
            kind=str(nav_action.get("k") or texts.KIND_HW),
            page=_num(nav_action, "p", -1),
            subject_page=_num(nav_action, "sp"),
            reply_to=reply_to,
        )
        return
    if action == "kind":
        if await state.get_state() != AddRecord.kind.state:
            return
        await state.update_data(kind=nav_action.get("kind"), attachments=[])
        await state.set_state(AddRecord.subject)
        await _show_pick_subjects(bot, chat_id, state, internal_chat_id, 0, reply_to)
        return
    if action == "pick_page":
        if await state.get_state() != AddRecord.subject.state:
            return
        await _show_pick_subjects(
            bot, chat_id, state, internal_chat_id, _num(nav_action, "p"), reply_to
        )
        return
    if action == "pick":
        if await state.get_state() != AddRecord.subject.state:
            return
        subject = await subjects_db.get_subject(_num(nav_action, "id"), internal_chat_id)
        if subject is None:
            await message.answer(texts.SUBJECT_NOT_FOUND)
            return
        await state.update_data(subject_id=subject["id"])
        await state.set_state(AddRecord.date)
        await nav.show_screen(
            bot,
            chat_id,
            state,
            texts.choose_date_text(subject["name"]),
            nav.rows_date(entering=False),
            reply_to=reply_to,
        )
        return
    if action == "date":
        if await state.get_state() not in DATE_STATES:
            return
        from datetime import date, timedelta

        picked = (date.today() + timedelta(days=_num(nav_action, "days"))).isoformat()
        await state.update_data(date=picked)
        await _go_text(bot, chat_id, state, internal_chat_id, reply_to=reply_to)
        return
    if action == "enter_date":
        if await state.get_state() != AddRecord.date.state:
            return
        await state.set_state(AddRecord.custom_date)
        await nav.show_screen(
            bot,
            chat_id,
            state,
            texts.DATE_FORMAT,
            nav.rows_date(entering=True),
            reply_to=reply_to,
        )
        return
    if action in {"done", "no_files"}:
        current = await state.get_state()
        if current == AddRecord.attachments.state:
            if action == "no_files":
                await state.update_data(attachments=[])
            await _show_preview(bot, chat_id, state, internal_chat_id, reply_to)
            return
        from bot.handlers.attachments import AddFiles

        if current == AddFiles.collecting.state:
            data = await state.get_data()
            items = list(data.get("attachments") or [])
            if not items:
                await message.answer(texts.NEED_FILE)
                return
            saved = await files.add_attachments(
                data["record_id"], internal_chat_id, db_user["id"], items
            )
            if not saved:
                await message.answer(texts.RECORD_NOT_FOUND)
                return
            await state.set_state(None)
            await show_card(
                bot,
                chat_id,
                internal_chat_id,
                int(data["record_id"]),
                role,
                state,
                kind=str(data.get("kind") or texts.KIND_HW),
                page=int(data.get("page") if data.get("page") is not None else -1),
                subject_page=int(data.get("subject_page") or 0),
                reply_to=reply_to,
            )
            await message.answer(texts.FILES_ADDED)
            return
    if action == "publish":
        if await state.get_state() != AddRecord.preview.state:
            return
        data = await state.get_data()
        kind = data.get("kind")
        date_iso = data.get("date") or ""
        if kind not in {texts.KIND_HW, texts.KIND_NOTE} or not texts.is_iso_date(date_iso):
            await nav.show_home(bot, chat_id, state, role, reply_to)
            return
        items = files.clean_items(list(data.get("attachments") or []))
        record_id = await records.create_record(
            internal_chat_id=internal_chat_id,
            subject_id=data["subject_id"],
            kind=kind,
            date_iso=date_iso,
            text=data.get("text") or "",
            internal_user_id=db_user["id"],
            attachments=items,
        )
        if record_id is None:
            await message.answer(texts.SUBJECT_NOT_FOUND)
            return
        view = await records.get_record(record_id, internal_chat_id)
        if view is not None:
            await message.answer(
                texts.card_text(
                    subject=view["subject_name"],
                    kind=view["kind"],
                    date_iso=view["date"],
                    body=view["text"] or "",
                    username=view["author_username"],
                    telegram_id=view["author_telegram_id"],
                    photos=int(view["photo_count"]),
                    documents=int(view["doc_count"]),
                )
            )
            stored = await files.list_attachments(record_id)
            if stored:
                await files.send_attachments(
                    bot,
                    chat_id,
                    stored,
                    header=texts.attachment_header(view["subject_name"], view["date"]),
                )
        await message.answer(texts.RECORD_ADDED)
        await nav.show_home(bot, chat_id, state, role, reply_to)
        return
    if action == "open_files":
        record = await records.get_record(_num(nav_action, "id"), internal_chat_id)
        if record is None:
            await message.answer(texts.RECORD_NOT_FOUND)
            return
        items = await files.list_attachments(record["id"])
        if not items:
            await message.answer(texts.NO_ATTACHMENTS)
            return
        data = await state.get_data()
        anchor = data.get("screen_message_id") or 0
        await files.hide_opened(bot, chat_id, anchor)
        sent = await files.send_attachments(
            bot,
            chat_id,
            items,
            header=texts.attachment_header(record["subject_name"], record["date"]),
        )
        files.remember_opened(chat_id, anchor, sent)
        if not sent:
            await message.answer(texts.SEND_FAILED)
        return
    if action == "add_files":
        if not can_edit(role):
            await message.answer(texts.NO_ACCESS)
            return
        from bot.handlers.attachments import AddFiles

        record = await records.get_record(_num(nav_action, "id"), internal_chat_id)
        if record is None:
            await message.answer(texts.RECORD_NOT_FOUND)
            return
        old_id = (await state.get_data()).get("screen_message_id")
        await state.set_state(AddFiles.collecting)
        await state.update_data(
            chat_id=chat_id,
            user_id=user_id,
            internal_chat_id=internal_chat_id,
            internal_user_id=db_user["id"],
            record_id=record["id"],
            kind=nav_action.get("k"),
            page=nav_action.get("p"),
            subject_page=nav_action.get("sp"),
            attachments=[],
            screen_message_id=old_id,
        )
        await nav.show_screen(
            bot,
            chat_id,
            state,
            texts.ask_more_files_screen(record["subject_name"], record["kind"], record["date"]),
            nav.rows_files(extra=True),
            reply_to=reply_to,
        )
        return
    if action == "list_files":
        record = await records.get_record(_num(nav_action, "id"), internal_chat_id)
        if record is None:
            await message.answer(texts.RECORD_NOT_FOUND)
            return
        items = await files.list_attachments(record["id"])
        buttons = []
        if can_edit(role):
            for index, item in enumerate(items, start=1):
                buttons.append([
                    nav.b(
                        f"{texts.BTN_DELETE} {index}",
                        "ask_delete_file",
                        "danger",
                        id=item["id"],
                        r=record["id"],
                        k=nav_action.get("k"),
                        p=nav_action.get("p"),
                        sp=nav_action.get("sp"),
                    )
                ])
        buttons.append([
            nav.b(
                texts.BTN_BACK,
                "back",
                to="card",
                r=record["id"],
                k=nav_action.get("k"),
                p=nav_action.get("p"),
                sp=nav_action.get("sp"),
            )
        ])
        await nav.show_screen(
            bot,
            chat_id,
            state,
            texts.attachment_list_text(items),
            buttons,
            reply_to=reply_to,
        )
        return
    if action == "ask_delete_file":
        if not can_edit(role):
            await message.answer(texts.NO_ACCESS)
            return
        row = await files.get_attachment(_num(nav_action, "id"), internal_chat_id)
        if row is None:
            await message.answer(texts.ATTACHMENT_NOT_FOUND)
            return
        position = await files.attachment_position(row["id"], row["record_id"])
        if position is None:
            await message.answer(texts.ATTACHMENT_NOT_FOUND)
            return
        index, total = position
        buttons = [
            [nav.b(texts.BTN_DELETE, "confirm_file", "danger", id=row["id"], y=1, r=row["record_id"], k=nav_action.get("k"), p=nav_action.get("p"), sp=nav_action.get("sp"))],
            [nav.b(texts.BTN_CANCEL, "confirm_file", id=row["id"], y=0, r=row["record_id"], k=nav_action.get("k"), p=nav_action.get("p"), sp=nav_action.get("sp"))],
        ]
        await nav.show_screen(
            bot,
            chat_id,
            state,
            texts.confirm_delete_attachment(index, total),
            buttons,
            reply_to=reply_to,
        )
        return
    if action == "confirm_file":
        if _num(nav_action, "y") == 0 or not can_edit(role):
            await show_card(
                bot,
                chat_id,
                internal_chat_id,
                _num(nav_action, "r"),
                role,
                state,
                kind=str(nav_action.get("k") or texts.KIND_HW),
                page=_num(nav_action, "p", -1),
                subject_page=_num(nav_action, "sp"),
                reply_to=reply_to,
            )
            return
        await files.delete_attachment(_num(nav_action, "id"), internal_chat_id)
        record = await records.get_record(_num(nav_action, "r"), internal_chat_id)
        items = await files.list_attachments(_num(nav_action, "r")) if record else []
        buttons = []
        if can_edit(role):
            for index, item in enumerate(items, start=1):
                buttons.append([
                    nav.b(
                        f"{texts.BTN_DELETE} {index}",
                        "ask_delete_file",
                        "danger",
                        id=item["id"],
                        r=_num(nav_action, "r"),
                        k=nav_action.get("k"),
                        p=nav_action.get("p"),
                        sp=nav_action.get("sp"),
                    )
                ])
        buttons.append([
            nav.b(
                texts.BTN_BACK,
                "back",
                to="card",
                r=_num(nav_action, "r"),
                k=nav_action.get("k"),
                p=nav_action.get("p"),
                sp=nav_action.get("sp"),
            )
        ])
        await nav.show_screen(
            bot, chat_id, state, texts.attachment_list_text(items), buttons, reply_to=reply_to
        )
        return
    if action == "edit_text":
        if not can_edit(role):
            await message.answer(texts.NO_ACCESS)
            return
        old_id = (await state.get_data()).get("screen_message_id")
        from bot.handlers.homework import EditText

        await state.set_state(EditText.waiting)
        await state.update_data(
            chat_id=chat_id,
            user_id=user_id,
            internal_chat_id=internal_chat_id,
            record_id=_num(nav_action, "id"),
            kind=nav_action.get("k"),
            page=nav_action.get("p"),
            subject_page=nav_action.get("sp"),
            screen_message_id=old_id,
        )
        await nav.show_screen(
            bot, chat_id, state, texts.ASK_NEW_TEXT, nav.rows_text(), reply_to=reply_to
        )
        return
    if action == "ask_delete_record":
        if not can_edit(role):
            await message.answer(texts.NO_ACCESS)
            return
        record = await records.get_record(_num(nav_action, "id"), internal_chat_id)
        if record is None:
            await message.answer(texts.RECORD_NOT_FOUND)
            return
        buttons = [
            [nav.b(texts.BTN_DELETE, "confirm_record", "danger", id=record["id"], y=1, k=nav_action.get("k"), p=nav_action.get("p"), sp=nav_action.get("sp"))],
            [nav.b(texts.BTN_CANCEL, "confirm_record", id=record["id"], y=0, k=nav_action.get("k"), p=nav_action.get("p"), sp=nav_action.get("sp"))],
        ]
        await nav.show_screen(
            bot,
            chat_id,
            state,
            texts.confirm_delete_record(record["kind"], record["subject_name"], record["date"]),
            buttons,
            reply_to=reply_to,
        )
        return
    if action == "confirm_record":
        if _num(nav_action, "y") == 1 and can_edit(role):
            await records.delete_record(_num(nav_action, "id"), internal_chat_id)
            await message.answer(texts.RECORD_DELETED)
            await nav.show_home(bot, chat_id, state, role, reply_to)
            return
        await show_card(
            bot,
            chat_id,
            internal_chat_id,
            _num(nav_action, "id"),
            role,
            state,
            kind=str(nav_action.get("k") or texts.KIND_HW),
            page=_num(nav_action, "p", -1),
            subject_page=_num(nav_action, "sp"),
            reply_to=reply_to,
        )
        return

