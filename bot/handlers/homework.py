from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.callbacks import (
    BackCB,
    ConfirmRecordCB,
    DelRecCB,
    EditCB,
    EditFormCB,
    FlowCB,
    PageCB,
    PickCB,
    RecordCB,
    SectionCB,
    SubjectCB,
    answer_callback,
    has_member,
)
from bot.db import can_edit, is_admin, user_lock
from bot.handlers.subjects import begin_subject_prompt
from bot.handlers import NotCommand, TextCommand
from bot import keyboards, nav, texts
from bot.services import attachments as files
from bot.services import homework as records
from bot.services import subjects as subjects_db

router = Router(name="homework")


class AddRecord(StatesGroup):
    kind = State()
    subject = State()
    date = State()
    custom_date = State()
    text = State()
    attachments = State()
    preview = State()


class EditText(StatesGroup):
    waiting = State()


ADD_STATES = {
    AddRecord.kind.state,
    AddRecord.subject.state,
    AddRecord.date.state,
    AddRecord.custom_date.state,
    AddRecord.text.state,
    AddRecord.attachments.state,
    AddRecord.preview.state,
}
DATE_STATES = {AddRecord.date.state, AddRecord.custom_date.state}


def _is_command(message: Message) -> bool:
    return bool(message.text and message.text.startswith("/"))


def _iso_shift(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


async def render_card(
    record_id: int,
    internal_chat_id: int,
    role: str | None,
    *,
    kind: str,
    page: int,
    subject_page: int,
):
    record = await records.get_record(record_id, internal_chat_id)
    if record is None:
        return None
    list_kind = kind if kind in {texts.KIND_HW, texts.KIND_NOTE, texts.KIND_ALL} else record["kind"]
    text = texts.card_text(
        subject=record["subject_name"],
        kind=record["kind"],
        date_iso=record["date"],
        body=record["text"] or "",
        username=record["author_username"],
        telegram_id=record["author_telegram_id"],
        photos=int(record["photo_count"]),
        documents=int(record["doc_count"]),
    )
    markup = keyboards.card_keyboard(
        record_id=record["id"],
        subject_id=record["subject_id"],
        role=role,
        photos=int(record["photo_count"]),
        documents=int(record["doc_count"]),
        kind=list_kind,
        page=page,
        subject_page=subject_page,
    )
    return text, markup


async def show_subjects(
    bot,
    chat_id: int,
    internal_chat_id: int,
    page: int = 0,
    message_id: int | None = None,
    role: str | None = None,
    state: FSMContext | None = None,
    reply_to: int | None = None,
) -> None:
    del message_id
    rows = await subjects_db.list_subjects(internal_chat_id)
    if state is None:
        return
    if not rows:
        buttons = []
        if is_admin(role):
            buttons.append([nav.b(texts.BTN_ADD_SUBJECT, "new_subject", "success")])
        await nav.show_screen(bot, chat_id, state, texts.NO_SUBJECTS, buttons, reply_to=reply_to)
        return
    pages = texts.page_count(len(rows))
    page = texts.clamp_page(page, pages)
    chunk = rows[page * texts.PAGE_SIZE : (page + 1) * texts.PAGE_SIZE]
    buttons = [
        [nav.b(texts.button_label(row["name"]), "subject", id=row["id"], p=page)]
        for row in chunk
    ]
    if page > 0:
        buttons.append([nav.b(texts.BTN_PREV, "subjects_page", p=page - 1)])
    if page + 1 < pages:
        buttons.append([nav.b(texts.BTN_NEXT, "subjects_page", p=page + 1)])
    if is_admin(role):
        buttons.append([nav.b(texts.BTN_ADD_SUBJECT, "new_subject", "success")])
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.choose_subject_text(page, pages, wizard=False),
        buttons,
        reply_to=reply_to,
    )


async def show_sections(
    bot,
    chat_id: int,
    internal_chat_id: int,
    subject_id: int,
    subject_page: int,
    message_id: int | None = None,
    state: FSMContext | None = None,
    reply_to: int | None = None,
) -> None:
    del message_id
    subject = await subjects_db.get_subject(subject_id, internal_chat_id)
    if state is None:
        return
    if subject is None:
        await nav.show_screen(bot, chat_id, state, texts.SUBJECT_NOT_FOUND, [], reply_to=reply_to)
        return
    buttons = [
        [
            nav.b(texts.BTN_HW, "section", s=subject["id"], k="dz", sp=subject_page),
            nav.b(texts.BTN_NOTE, "section", s=subject["id"], k="note", sp=subject_page),
        ],
        [nav.b(texts.BTN_ALL, "section", s=subject["id"], k="all", sp=subject_page)],
        [nav.b(texts.BTN_BACK, "back", to="sub", p=subject_page)],
    ]
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.sections_text(subject["name"]),
        buttons,
        reply_to=reply_to,
    )


async def show_records(
    bot,
    chat_id: int,
    internal_chat_id: int,
    subject_id: int,
    kind: str,
    page: int,
    subject_page: int,
    message_id: int | None = None,
    state: FSMContext | None = None,
    reply_to: int | None = None,
) -> None:
    del message_id
    if state is None:
        return
    if kind not in {texts.KIND_HW, texts.KIND_NOTE, texts.KIND_ALL}:
        await nav.show_screen(bot, chat_id, state, texts.STALE, [], reply_to=reply_to)
        return
    subject = await subjects_db.get_subject(subject_id, internal_chat_id)
    if subject is None:
        await nav.show_screen(bot, chat_id, state, texts.SUBJECT_NOT_FOUND, [], reply_to=reply_to)
        return
    kind_filter = None if kind == texts.KIND_ALL else kind
    total = await records.count_records(subject["id"], kind_filter)
    top = page < 0
    if top:
        rows = await records.list_records(
            subject["id"],
            kind_filter,
            limit=texts.TOP_LIMIT,
            offset=0,
        )
        view_page = -1
        pages = 1
    else:
        pages = texts.page_count(total)
        view_page = texts.clamp_page(page, pages) if total else 0
        rows = await records.list_records(
            subject["id"],
            kind_filter,
            limit=texts.PAGE_SIZE,
            offset=view_page * texts.PAGE_SIZE,
        )
    text = texts.records_text(
        subject["name"],
        kind,
        empty=total == 0,
        page=0 if top else view_page,
        pages=1 if top else pages,
    )
    if state is None:
        return
    buttons = []
    for row in rows:
        label_kind = row["kind"] if kind == "all" else None
        buttons.append([
            nav.b(
                texts.record_button_text(row["date"], row["text"], label_kind),
                "record",
                id=row["id"],
                k=kind,
                p=view_page,
                sp=subject_page,
            )
        ])
    if top and total > texts.TOP_LIMIT:
        buttons.append([
            nav.b(texts.BTN_SHOW_ALL, "records_page", s=subject["id"], k=kind, p=0, sp=subject_page)
        ])
    if not top:
        record_pages = texts.page_count(total)
        if view_page > 0:
            buttons.append([
                nav.b(
                    texts.BTN_PREV,
                    "records_page",
                    s=subject["id"],
                    k=kind,
                    p=view_page - 1,
                    sp=subject_page,
                )
            ])
        if view_page + 1 < record_pages:
            buttons.append([
                nav.b(
                    texts.BTN_NEXT,
                    "records_page",
                    s=subject["id"],
                    k=kind,
                    p=view_page + 1,
                    sp=subject_page,
                )
            ])
    buttons.append([
        nav.b(texts.BTN_BACK, "back", to="sec", s=subject["id"], sp=subject_page)
    ])
    await nav.show_screen(bot, chat_id, state, text, buttons, reply_to=reply_to)


async def begin_add(
    bot,
    chat_id: int,
    user_id: int,
    internal_chat_id: int,
    internal_user_id: int,
    state: FSMContext,
    message_id: int | None = None,
    role: str | None = None,
    reply_to: int | None = None,
) -> None:
    del message_id
    old_id = (await state.get_data()).get("screen_message_id")
    rows = await subjects_db.list_subjects(internal_chat_id)
    if not rows:
        if is_admin(role):
            await begin_subject_prompt(
                bot,
                chat_id,
                user_id,
                internal_chat_id,
                internal_user_id,
                state,
                reply_to=reply_to,
            )
            return
        await state.set_data({"screen_message_id": old_id})
        await nav.show_screen(bot, chat_id, state, texts.NO_SUBJECTS, [], reply_to=reply_to)
        return
    await state.set_state(AddRecord.kind)
    await state.set_data(
        {
            "screen_message_id": old_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "internal_chat_id": internal_chat_id,
            "internal_user_id": internal_user_id,
            "attachments": [],
        }
    )
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.choose_kind_text(),
        nav.rows_kind(),
        reply_to=reply_to,
    )


async def _drop_flow(state: FSMContext, bot, chat_id: int) -> None:
    await keyboards.clear_step_keyboard(bot, chat_id, state)
    await state.clear()


async def _owns(state: FSMContext, callback: CallbackQuery) -> dict | None:
    data = await state.get_data()
    if data.get("user_id") != callback.from_user.id:
        return None
    if callback.message is not None and data.get("chat_id") != callback.message.chat.id:
        return None
    return data


async def _show_pick_subjects(
    bot,
    chat_id: int,
    state: FSMContext,
    internal_chat_id: int,
    page: int,
    reply_to: int | None = None,
) -> None:
    rows = await subjects_db.list_subjects(internal_chat_id)
    if not rows:
        await nav.show_home(bot, chat_id, state, None, reply_to)
        return
    pages = texts.page_count(len(rows))
    page = texts.clamp_page(page, pages)
    chunk = rows[page * texts.PAGE_SIZE : (page + 1) * texts.PAGE_SIZE]
    buttons = [
        [nav.b(texts.button_label(row["name"]), "pick", id=row["id"])]
        for row in chunk
    ]
    if page > 0:
        buttons.append([nav.b(texts.BTN_PREV, "pick_page", p=page - 1)])
    if page + 1 < pages:
        buttons.append([nav.b(texts.BTN_NEXT, "pick_page", p=page + 1)])
    buttons.append([nav.b(texts.BTN_CANCEL, "cancel")])
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.choose_subject_text(page, pages, wizard=True),
        buttons,
        reply_to=reply_to,
    )


async def _go_text(
    bot,
    chat_id: int,
    state: FSMContext,
    internal_chat_id: int,
    *,
    reply_to: int | None = None,
) -> None:
    data = await state.get_data()
    subject = await subjects_db.get_subject(data.get("subject_id") or 0, internal_chat_id)
    if subject is None or not texts.is_iso_date(data.get("date") or ""):
        await nav.show_home(bot, chat_id, state, None, reply_to)
        return
    await state.set_state(AddRecord.text)
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.ask_text_screen(subject["name"], data["kind"], data["date"]),
        nav.rows_text(),
        reply_to=reply_to,
    )


async def _show_preview(
    bot,
    chat_id: int,
    state: FSMContext,
    internal_chat_id: int,
    reply_to: int | None = None,
) -> None:
    data = await state.get_data()
    subject = await subjects_db.get_subject(data.get("subject_id") or 0, internal_chat_id)
    if subject is None:
        await state.clear()
        await keyboards.edit_or_send(bot, chat_id, texts.SUBJECT_NOT_FOUND, keyboards.back_menu())
        return
    photos, documents = files.count_types(list(data.get("attachments") or []))
    await state.set_state(AddRecord.preview)
    await nav.show_screen(
        bot,
        chat_id,
        state,
        texts.preview_text(
            subject=subject["name"],
            kind=data.get("kind") or "",
            date_iso=data.get("date") or "",
            body=data.get("text") or "",
            photos=photos,
            documents=documents,
        ),
        nav.rows_preview(),
        reply_to=reply_to,
    )


async def _publish(callback: CallbackQuery, state: FSMContext, role: str | None) -> None:
    message = callback.message
    if message is None or callback.from_user is None:
        return
    chat_id = message.chat.id
    async with user_lock(chat_id, callback.from_user.id):
        data = await state.get_data()
        if await state.get_state() != AddRecord.preview.state or data.get("publishing"):
            return
        await state.update_data(publishing=True)
        kind = data.get("kind")
        date_iso = data.get("date") or ""
        if kind not in {texts.KIND_HW, texts.KIND_NOTE} or not texts.is_iso_date(date_iso):
            await state.clear()
            await keyboards.edit_or_send(
                callback.bot,
                chat_id,
                texts.STALE,
                keyboards.main_menu(role),
                data.get("bot_message_id"),
            )
            return
        items = files.clean_items(list(data.get("attachments") or []))
        try:
            record_id = await records.create_record(
                internal_chat_id=data["internal_chat_id"],
                subject_id=data["subject_id"],
                kind=kind,
                date_iso=date_iso,
                text=data.get("text") or "",
                internal_user_id=data["internal_user_id"],
                attachments=items,
            )
        except Exception:
            await state.update_data(publishing=False)
            raise
        if record_id is None:
            await state.update_data(publishing=False)
            await message.answer(texts.SUBJECT_NOT_FOUND)
            return
        preview_id = data.get("bot_message_id")
        internal_chat_id = data["internal_chat_id"]
        await state.clear()
    rendered = await render_card(
        record_id,
        internal_chat_id,
        role,
        kind=kind,
        page=-1,
        subject_page=0,
    )
    if rendered is not None:
        text, markup = rendered
        await keyboards.edit_or_send(callback.bot, chat_id, text, markup, preview_id)
    stored = await files.list_attachments(record_id)
    if stored:
        view = await records.get_record(record_id, internal_chat_id)
        header = None
        if view is not None:
            header = texts.attachment_header(view["subject_name"], view["date"])
        sent = await files.send_attachments(callback.bot, chat_id, stored, header=header)
        if not sent:
            await message.answer(texts.SEND_FAILED)
    await message.answer(texts.RECORD_ADDED)


@router.message(TextCommand(texts.CMD_ADD))
async def cmd_add(
    message: Message,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if not has_member(internal_chat_id, db_user) or internal_chat_id is None or db_user is None:
        await message.answer(texts.PRIVATE)
        return
    if not can_edit(role):
        await message.answer(texts.NO_ACCESS)
        return
    if message.from_user is None:
        return
    await begin_add(
        message.bot,
        message.chat.id,
        message.from_user.id,
        internal_chat_id,
        db_user["id"],
        state,
        role=role,
        reply_to=message.message_id,
    )


@router.callback_query(FlowCB.filter())
async def on_flow(
    callback: CallbackQuery,
    callback_data: FlowCB,
    state: FSMContext,
    role: str | None,
    db_user,
    internal_chat_id: int | None,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    current = await state.get_state()
    data = await _owns(state, callback)
    if current not in ADD_STATES or data is None:
        await answer_callback(callback, texts.STALE)
        return
    if not can_edit(role):
        await answer_callback(callback, texts.NO_ACCESS)
        await state.clear()
        return
    action = callback_data.a
    chat_id = callback.message.chat.id
    await answer_callback(callback)
    if action == "cancel":
        await nav.show_home(callback.bot, chat_id, state, role, None)
        return
    if action in {"dz", "note"}:
        if current != AddRecord.kind.state:
            return
        await state.update_data(kind=action, attachments=[])
        await state.set_state(AddRecord.subject)
        await _show_pick_subjects(callback.bot, chat_id, state, internal_chat_id, 0)
        return
    if action in {"today", "tomorrow"}:
        if current not in DATE_STATES:
            return
        await state.update_data(date=_iso_shift(0 if action == "today" else 1))
        await _go_text(callback.bot, chat_id, state, internal_chat_id)
        return
    if action == "enter_date":
        if current != AddRecord.date.state:
            return
        await state.set_state(AddRecord.custom_date)
        await nav.show_screen(
            callback.bot,
            chat_id,
            state,
            texts.DATE_FORMAT,
            nav.rows_date(entering=True),
        )
        return
    if action in {"done", "no_files"}:
        if current != AddRecord.attachments.state:
            return
        if action == "no_files":
            await state.update_data(attachments=[])
        await _show_preview(callback.bot, chat_id, state, internal_chat_id, None)
        return
    if action == "publish":
        if current != AddRecord.preview.state:
            return
        await _publish(callback, state, role)
        return


@router.callback_query(PageCB.filter())
async def on_page(
    callback: CallbackQuery,
    callback_data: PageCB,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if callback_data.c not in {"add", "sub", "rec"}:
        await answer_callback(callback, texts.STALE)
        return
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    if callback_data.c == "add":
        if await state.get_state() != AddRecord.subject.state or await _owns(state, callback) is None:
            await answer_callback(callback, texts.STALE)
            return
        await answer_callback(callback)
        await _show_pick_subjects(
            callback.bot,
            chat_id,
            state,
            internal_chat_id,
            callback_data.p,
        )
        return
    await _drop_flow(state, callback.bot, chat_id)
    await answer_callback(callback)
    if callback_data.c == "sub":
        await show_subjects(
            callback.bot, chat_id, internal_chat_id, callback_data.p, message_id, role, state
        )
        return
    await show_records(
        callback.bot,
        chat_id,
        internal_chat_id,
        callback_data.s,
        callback_data.k,
        callback_data.p,
        callback_data.sp,
        message_id,
        state,
    )


@router.callback_query(PickCB.filter())
async def pick_subject(
    callback: CallbackQuery,
    callback_data: PickCB,
    state: FSMContext,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if await state.get_state() != AddRecord.subject.state or await _owns(state, callback) is None:
        await answer_callback(callback, texts.STALE)
        return
    subject = await subjects_db.get_subject(callback_data.id, internal_chat_id)
    if subject is None:
        await answer_callback(callback, texts.SUBJECT_NOT_FOUND)
        return
    await state.update_data(subject_id=subject["id"])
    await state.set_state(AddRecord.date)
    await answer_callback(callback)
    await nav.show_screen(
        callback.bot,
        callback.message.chat.id,
        state,
        texts.choose_date_text(subject["name"]),
        nav.rows_date(entering=False),
    )


@router.callback_query(SubjectCB.filter())
async def open_subject(
    callback: CallbackQuery,
    callback_data: SubjectCB,
    state: FSMContext,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    await _drop_flow(state, callback.bot, callback.message.chat.id)
    await answer_callback(callback)
    await show_sections(
        callback.bot,
        callback.message.chat.id,
        internal_chat_id,
        callback_data.id,
        callback_data.p,
        callback.message.message_id,
        state,
    )


@router.callback_query(SectionCB.filter())
async def open_section(
    callback: CallbackQuery,
    callback_data: SectionCB,
    state: FSMContext,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    await _drop_flow(state, callback.bot, callback.message.chat.id)
    await answer_callback(callback)
    await show_records(
        callback.bot,
        callback.message.chat.id,
        internal_chat_id,
        callback_data.subject_id,
        callback_data.kind,
        -1,
        callback_data.sp,
        callback.message.message_id,
        state,
    )


@router.callback_query(RecordCB.filter())
async def show_card(
    bot,
    chat_id: int,
    internal_chat_id: int,
    record_id: int,
    role: str | None,
    state: FSMContext,
    *,
    kind: str,
    page: int,
    subject_page: int,
    reply_to: int | None = None,
) -> None:
    record = await records.get_record(record_id, internal_chat_id)
    if record is None:
        await nav.show_screen(bot, chat_id, state, texts.RECORD_NOT_FOUND, [], reply_to=reply_to)
        return
    text = texts.card_text(
        subject=record["subject_name"],
        kind=record["kind"],
        date_iso=record["date"],
        body=record["text"] or "",
        username=record["author_username"],
        telegram_id=record["author_telegram_id"],
        photos=int(record["photo_count"]),
        documents=int(record["doc_count"]),
    )
    photos = int(record["photo_count"])
    documents = int(record["doc_count"])
    manager = can_edit(role)
    buttons: list[list[dict]] = []
    if photos + documents:
        buttons.append([nav.b(texts.BTN_OPEN_FILES, "open_files", id=record["id"])])
    if manager:
        buttons.append([
            nav.b(
                texts.BTN_ADD_FILES,
                "add_files",
                id=record["id"],
                k=kind,
                p=page,
                sp=subject_page,
            )
        ])
        if photos + documents:
            buttons.append([
                nav.b(
                    texts.BTN_FILES,
                    "list_files",
                    id=record["id"],
                    k=kind,
                    p=page,
                    sp=subject_page,
                )
            ])
        buttons.append([
            nav.b(
                texts.BTN_EDIT_TEXT,
                "edit_text",
                id=record["id"],
                k=kind,
                p=page,
                sp=subject_page,
            )
        ])
        buttons.append([
            nav.b(
                texts.BTN_DELETE_RECORD,
                "ask_delete_record",
                "danger",
                id=record["id"],
                k=kind,
                p=page,
                sp=subject_page,
            )
        ])
    buttons.append([
        nav.b(
            texts.BTN_BACK,
            "back",
            to="rec",
            s=record["subject_id"],
            k=kind,
            p=page,
            sp=subject_page,
        )
    ])
    await nav.show_screen(bot, chat_id, state, text, buttons, reply_to=reply_to)


async def open_record(
    callback: CallbackQuery,
    callback_data: RecordCB,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    await answer_callback(callback)
    await show_card(
        callback.bot,
        callback.message.chat.id,
        internal_chat_id,
        callback_data.id,
        role,
        state,
        kind=callback_data.k,
        page=callback_data.p,
        subject_page=callback_data.sp,
    )


@router.callback_query(BackCB.filter())
async def on_back(
    callback: CallbackQuery,
    callback_data: BackCB,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    await _drop_flow(state, callback.bot, callback.message.chat.id)
    await answer_callback(callback)
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    await files.hide_opened(callback.bot, chat_id, message_id)
    target = callback_data.to
    if target == "sub":
        await show_subjects(
            callback.bot, chat_id, internal_chat_id, callback_data.p, message_id, role, state
        )
        return
    if target == "sec":
        await show_sections(
            callback.bot,
            chat_id,
            internal_chat_id,
            callback_data.s,
            callback_data.sp,
            message_id,
            state,
        )
        return
    if target == "rec":
        await show_records(
            callback.bot,
            chat_id,
            internal_chat_id,
            callback_data.s,
            callback_data.k,
            callback_data.p,
            callback_data.sp,
            message_id,
            state,
        )
        return
    if target == "card":
        rendered = await render_card(
            callback_data.r,
            internal_chat_id,
            role,
            kind=callback_data.k,
            page=callback_data.p,
            subject_page=callback_data.sp,
        )
        if rendered is None:
            await keyboards.edit_or_send(
                callback.bot,
                chat_id,
                texts.RECORD_NOT_FOUND,
                keyboards.back_menu(),
                message_id,
            )
            return
        text, markup = rendered
        await keyboards.edit_or_send(callback.bot, chat_id, text, markup, message_id)
        return
    await keyboards.edit_or_send(
        callback.bot,
        chat_id,
        texts.MAIN_MENU,
        keyboards.main_menu(role),
        message_id,
    )


@router.callback_query(EditCB.filter())
async def start_edit_text(
    callback: CallbackQuery,
    callback_data: EditCB,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if not can_edit(role) or db_user is None or callback.from_user is None:
        await answer_callback(callback, texts.NO_ACCESS)
        return
    record = await records.get_record(callback_data.id, internal_chat_id)
    if record is None:
        await answer_callback(callback)
        await keyboards.edit_or_send(
            callback.bot,
            callback.message.chat.id,
            texts.RECORD_NOT_FOUND,
            keyboards.back_menu(),
            callback.message.message_id,
        )
        return
    await state.set_state(EditText.waiting)
    await state.set_data(
        {
            "chat_id": callback.message.chat.id,
            "user_id": callback.from_user.id,
            "internal_chat_id": internal_chat_id,
            "record_id": record["id"],
            "kind": callback_data.k,
            "page": callback_data.p,
            "subject_page": callback_data.sp,
            "bot_message_id": callback.message.message_id,
        }
    )
    await answer_callback(callback)
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        texts.ASK_NEW_TEXT,
        keyboards.edit_text_keyboard(),
        callback.message.message_id,
    )


@router.callback_query(EditFormCB.filter())
async def cancel_edit_text(
    callback: CallbackQuery,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user):
        await answer_callback(callback, texts.STALE)
        return
    if await state.get_state() != EditText.waiting.state or await _owns(state, callback) is None:
        await answer_callback(callback, texts.STALE)
        return
    await state.clear()
    await answer_callback(callback)
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        texts.MAIN_MENU,
        keyboards.main_menu(role),
        callback.message.message_id,
    )


@router.message(EditText.waiting, F.text, NotCommand())
async def save_text(
    message: Message,
    state: FSMContext,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if _is_command(message):
        return
    if not can_edit(role) or internal_chat_id is None or db_user is None:
        await state.clear()
        await message.answer(texts.NO_ACCESS)
        return
    data = await state.get_data()
    if message.from_user is None or data.get("user_id") != message.from_user.id:
        return
    status, body = texts.normalize_text(message.text or "")
    if status == "long":
        await message.answer(texts.TEXT_TOO_LONG)
        return
    if status == "empty":
        await message.answer(texts.ASK_NEW_TEXT)
        return
    updated = await records.update_text(data["record_id"], internal_chat_id, body)
    if not updated:
        await state.clear()
        await message.answer(texts.RECORD_NOT_FOUND)
        return
    rendered = await render_card(
        data["record_id"],
        internal_chat_id,
        role,
        kind=data.get("kind") or texts.KIND_HW,
        page=int(data.get("page") if data.get("page") is not None else -1),
        subject_page=int(data.get("subject_page") or 0),
    )
    await state.clear()
    if rendered is None:
        await message.answer(texts.RECORD_NOT_FOUND)
        return
    text, markup = rendered
    await keyboards.edit_or_send(
        message.bot,
        message.chat.id,
        text,
        markup,
        data.get("bot_message_id"),
    )


@router.message(EditText.waiting, NotCommand())
async def edit_text_other(message: Message) -> None:
    if _is_command(message):
        return
    await message.answer(texts.ASK_NEW_TEXT)


@router.callback_query(DelRecCB.filter())
async def ask_delete_record(
    callback: CallbackQuery,
    callback_data: DelRecCB,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if not can_edit(role):
        await answer_callback(callback, texts.NO_ACCESS)
        return
    record = await records.get_record(callback_data.id, internal_chat_id)
    if record is None:
        await answer_callback(callback)
        await keyboards.edit_or_send(
            callback.bot,
            callback.message.chat.id,
            texts.RECORD_NOT_FOUND,
            keyboards.back_menu(),
            callback.message.message_id,
        )
        return
    yes = ConfirmRecordCB(
        id=record["id"],
        y=1,
        k=callback_data.k,
        p=callback_data.p,
        sp=callback_data.sp,
    ).pack()
    no = ConfirmRecordCB(
        id=record["id"],
        y=0,
        k=callback_data.k,
        p=callback_data.p,
        sp=callback_data.sp,
    ).pack()
    await answer_callback(callback)
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        texts.confirm_delete_record(record["kind"], record["subject_name"], record["date"]),
        keyboards.confirm_keyboard(yes, no),
        callback.message.message_id,
    )


@router.callback_query(ConfirmRecordCB.filter())
async def confirm_delete_record(
    callback: CallbackQuery,
    callback_data: ConfirmRecordCB,
    role: str | None,
    internal_chat_id: int | None,
    db_user,
) -> None:
    if callback.message is None or not has_member(internal_chat_id, db_user) or internal_chat_id is None:
        await answer_callback(callback, texts.STALE)
        return
    if callback_data.y == 0:
        rendered = await render_card(
            callback_data.id,
            internal_chat_id,
            role,
            kind=callback_data.k,
            page=callback_data.p,
            subject_page=callback_data.sp,
        )
        await answer_callback(callback)
        if rendered is None:
            await keyboards.edit_or_send(
                callback.bot,
                callback.message.chat.id,
                texts.RECORD_NOT_FOUND,
                keyboards.back_menu(),
                callback.message.message_id,
            )
            return
        text, markup = rendered
        await keyboards.edit_or_send(
            callback.bot,
            callback.message.chat.id,
            text,
            markup,
            callback.message.message_id,
        )
        return
    if not can_edit(role):
        await answer_callback(callback, texts.NO_ACCESS)
        return
    deleted = await records.delete_record(callback_data.id, internal_chat_id)
    await answer_callback(callback)
    text = texts.RECORD_DELETED if deleted else texts.RECORD_NOT_FOUND
    await keyboards.edit_or_send(
        callback.bot,
        callback.message.chat.id,
        text,
        keyboards.back_menu(),
        callback.message.message_id,
    )


@router.message(AddRecord.custom_date, F.text, NotCommand())
async def custom_date(message: Message, state: FSMContext, internal_chat_id: int | None) -> None:
    if _is_command(message) or internal_chat_id is None or message.from_user is None:
        return
    data = await state.get_data()
    if data.get("user_id") != message.from_user.id:
        return
    parsed = texts.parse_user_date(message.text or "")
    if parsed is None:
        await nav.show_screen(
            message.bot,
            message.chat.id,
            state,
            texts.DATE_FORMAT,
            nav.rows_date(entering=True),
            reply_to=message.message_id,
        )
        return
    await state.update_data(date=parsed)
    await _go_text(
        message.bot,
        message.chat.id,
        state,
        internal_chat_id,
        reply_to=message.message_id,
    )


@router.message(AddRecord.text, F.text, NotCommand())
async def record_text(message: Message, state: FSMContext, internal_chat_id: int | None) -> None:
    if _is_command(message) or internal_chat_id is None or message.from_user is None:
        return
    data = await state.get_data()
    if data.get("user_id") != message.from_user.id:
        return
    status, body = texts.normalize_text(message.text or "")
    if status != "ok":
        subject = await subjects_db.get_subject(data.get("subject_id") or 0, internal_chat_id)
        name = subject["name"] if subject is not None else ""
        kind = data.get("kind") or texts.KIND_HW
        date_iso = data.get("date") or ""
        prompt = texts.ask_text_screen(name, kind, date_iso)
        if status == "long":
            prompt = f"{texts.TEXT_TOO_LONG}\n{prompt}"
        await nav.show_screen(
            message.bot,
            message.chat.id,
            state,
            prompt,
            nav.rows_text(),
            reply_to=message.message_id,
        )
        return
    await state.update_data(text=body, attachments=[])
    await state.set_state(AddRecord.attachments)
    subject = await subjects_db.get_subject(data.get("subject_id") or 0, internal_chat_id)
    if subject is None:
        await state.clear()
        await message.answer(texts.SUBJECT_NOT_FOUND)
        return
    await nav.show_screen(
        message.bot,
        message.chat.id,
        state,
        texts.ask_files_screen(subject["name"], data.get("kind") or "", data.get("date") or ""),
        nav.rows_files(),
        reply_to=message.message_id,
    )


@router.message(AddRecord.attachments, F.photo)
@router.message(AddRecord.attachments, F.document)
async def collect_files(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.from_user is None or data.get("user_id") != message.from_user.id:
        return
    saved = await files.remember_file(state, message)
    if saved or not files.should_warn(message.chat.id, message.from_user.id, message.media_group_id):
        return
    await message.answer(texts.SEND_FILE)


@router.message(AddRecord.attachments, NotCommand())
async def files_other(message: Message) -> None:
    if _is_command(message) or message.from_user is None:
        return
    if not files.should_warn(message.chat.id, message.from_user.id, message.media_group_id):
        return
    await message.answer(texts.SEND_FILE)


@router.message(AddRecord.preview, NotCommand())
async def preview_other(message: Message) -> None:
    if _is_command(message):
        return
    await message.answer(texts.PREVIEW_WAIT)


@router.message(AddRecord.kind, NotCommand())
@router.message(AddRecord.subject, NotCommand())
@router.message(AddRecord.date, NotCommand())
@router.message(AddRecord.custom_date, NotCommand())
async def wizard_buttons_only(message: Message) -> None:
    if _is_command(message):
        return
    await message.answer(texts.CHOOSE_BUTTON)
