from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callbacks import (
    AddFilesCB,
    BackCB,
    DelRecCB,
    DeleteAttachCB,
    EditCB,
    EditFormCB,
    FilesCB,
    FlowCB,
    ListAttachCB,
    MenuCB,
    OpenAttachCB,
    PageCB,
    PickCB,
    RecordCB,
    SectionCB,
    SubjectCB,
    SubjectFormCB,
)
from bot import texts

EMPTY_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[])


def quick_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_ABOUT)],
            [KeyboardButton(text=texts.BTN_RECORDS)],
            [KeyboardButton(text=texts.BTN_ADD)],
            [KeyboardButton(text=texts.BTN_SUBJECTS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_menu(role: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=texts.BTN_ABOUT, callback_data=MenuCB(a="about").pack())
    kb.button(text=texts.BTN_RECORDS, callback_data=MenuCB(a="records").pack())
    if role in {"admin", "editor"}:
        kb.button(text=texts.BTN_ADD, callback_data=MenuCB(a="add").pack())
    if role == "admin":
        kb.button(text=texts.BTN_SUBJECTS, callback_data=MenuCB(a="subjects").pack())
    kb.adjust(1)
    return kb.as_markup()


def subjects_actions(role: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if role == "admin":
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_ADD_SUBJECT,
                callback_data=MenuCB(a="new_subject").pack(),
            )
        )
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_BACK,
            callback_data=MenuCB(a="home").pack(),
        )
    )
    return kb.as_markup()


def back_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_BACK,
            callback_data=MenuCB(a="home").pack(),
        )
    )
    return kb.as_markup()


def subject_keyboard(rows: list, page: int, *, mode: str, role: str | None = None) -> InlineKeyboardMarkup:
    pages = texts.page_count(len(rows))
    page = texts.clamp_page(page, pages)
    start = page * texts.PAGE_SIZE
    chunk = rows[start : start + texts.PAGE_SIZE]
    kb = InlineKeyboardBuilder()
    context = "add" if mode == "add" else "sub"
    for row in chunk:
        if mode == "add":
            data = PickCB(id=row["id"]).pack()
        else:
            data = SubjectCB(id=row["id"], p=page).pack()
        kb.button(text=texts.button_label(row["name"]), callback_data=data)
    if chunk:
        kb.adjust(1)
    if pages > 1 and page > 0:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_PREV,
                callback_data=PageCB(p=page - 1, c=context, s=0, k="-", sp=0).pack(),
            )
        )
    if pages > 1 and page + 1 < pages:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_NEXT,
                callback_data=PageCB(p=page + 1, c=context, s=0, k="-", sp=0).pack(),
            )
        )
    if mode == "add":
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_CANCEL,
                callback_data=FlowCB(a="cancel").pack(),
            )
        )
    else:
        if role == "admin":
            kb.row(
                InlineKeyboardButton(
                    text=texts.BTN_ADD_SUBJECT,
                    callback_data=MenuCB(a="new_subject").pack(),
                )
            )
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_BACK,
                callback_data=MenuCB(a="home").pack(),
            )
        )
    return kb.as_markup()


def kind_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=texts.BTN_HW, callback_data=FlowCB(a="dz").pack()))
    kb.row(InlineKeyboardButton(text=texts.BTN_NOTE, callback_data=FlowCB(a="note").pack()))
    kb.row(InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=FlowCB(a="cancel").pack()))
    return kb.as_markup()


def date_keyboard(*, entering: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=texts.BTN_TODAY, callback_data=FlowCB(a="today").pack()))
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_TOMORROW,
            callback_data=FlowCB(a="tomorrow").pack(),
        )
    )
    if not entering:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_ENTER_DATE,
                callback_data=FlowCB(a="enter_date").pack(),
            )
        )
    kb.row(
        InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=FlowCB(a="cancel").pack())
    )
    return kb.as_markup()


def text_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=FlowCB(a="cancel").pack())
    )
    return kb.as_markup()


def files_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=texts.BTN_DONE, callback_data=FlowCB(a="done").pack()))
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_NO_FILES,
            callback_data=FlowCB(a="no_files").pack(),
        )
    )
    kb.row(
        InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=FlowCB(a="cancel").pack())
    )
    return kb.as_markup()


def preview_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_PUBLISH,
            callback_data=FlowCB(a="publish").pack(),
        )
    )
    kb.row(InlineKeyboardButton(text=texts.BTN_ABORT, callback_data=FlowCB(a="cancel").pack()))
    return kb.as_markup()


def sections_keyboard(subject_id: int, subject_page: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_HW,
            callback_data=SectionCB(subject_id=subject_id, kind="dz", sp=subject_page).pack(),
        )
    )
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_NOTE,
            callback_data=SectionCB(
                subject_id=subject_id,
                kind="note",
                sp=subject_page,
            ).pack(),
        )
    )
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_ALL,
            callback_data=SectionCB(subject_id=subject_id, kind="all", sp=subject_page).pack(),
        )
    )
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_BACK,
            callback_data=BackCB(to="sub", s=0, k="-", p=subject_page, r=0, sp=0).pack(),
        )
    )
    return kb.as_markup()


def records_keyboard(
    rows: list,
    *,
    subject_id: int,
    kind: str,
    page: int,
    subject_page: int,
    total: int,
    show_all_button: bool,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for row in rows:
        label_kind = row["kind"] if kind == "all" else None
        kb.row(
            InlineKeyboardButton(
                text=texts.record_button_text(row["date"], row["text"], label_kind),
                callback_data=RecordCB(
                    id=row["id"],
                    k=kind,
                    p=page,
                    sp=subject_page,
                ).pack(),
            )
        )
    if show_all_button and total > texts.TOP_LIMIT:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_SHOW_ALL,
                callback_data=PageCB(
                    p=0,
                    c="rec",
                    s=subject_id,
                    k=kind,
                    sp=subject_page,
                ).pack(),
            )
        )
    if page >= 0:
        pages = texts.page_count(total)
        if page > 0:
            kb.row(
                InlineKeyboardButton(
                    text=texts.BTN_PREV,
                    callback_data=PageCB(
                        p=page - 1,
                        c="rec",
                        s=subject_id,
                        k=kind,
                        sp=subject_page,
                    ).pack(),
                )
            )
        if page + 1 < pages:
            kb.row(
                InlineKeyboardButton(
                    text=texts.BTN_NEXT,
                    callback_data=PageCB(
                        p=page + 1,
                        c="rec",
                        s=subject_id,
                        k=kind,
                        sp=subject_page,
                    ).pack(),
                )
            )
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_BACK,
            callback_data=BackCB(
                to="sec",
                s=subject_id,
                k="-",
                p=0,
                r=0,
                sp=subject_page,
            ).pack(),
        )
    )
    return kb.as_markup()


def card_keyboard(
    *,
    record_id: int,
    subject_id: int,
    role: str | None,
    photos: int,
    documents: int,
    kind: str,
    page: int,
    subject_page: int,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    has_files = photos + documents > 0
    manager = role in {"admin", "editor"}
    back = BackCB(to="rec", s=subject_id, k=kind, p=page, r=0, sp=subject_page).pack()
    if has_files and not manager:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_OPEN_FILES,
                callback_data=OpenAttachCB(record_id=record_id).pack(),
            )
        )
        kb.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=back))
        return kb.as_markup()
    if has_files:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_OPEN_FILES,
                callback_data=OpenAttachCB(record_id=record_id).pack(),
            )
        )
    if manager:
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_ADD_FILES,
                callback_data=AddFilesCB(
                    id=record_id,
                    k=kind,
                    p=page,
                    sp=subject_page,
                ).pack(),
            )
        )
        if has_files:
            kb.row(
                InlineKeyboardButton(
                    text=texts.BTN_FILES,
                    callback_data=ListAttachCB(
                        record_id=record_id,
                        k=kind,
                        p=page,
                        sp=subject_page,
                    ).pack(),
                )
            )
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_EDIT_TEXT,
                callback_data=EditCB(
                    id=record_id,
                    k=kind,
                    p=page,
                    sp=subject_page,
                ).pack(),
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=texts.BTN_DELETE_RECORD,
                callback_data=DelRecCB(
                    id=record_id,
                    k=kind,
                    p=page,
                    sp=subject_page,
                ).pack(),
            )
        )
    kb.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=back))
    return kb.as_markup()


def attachments_keyboard(
    items: list,
    *,
    role: str | None,
    record_id: int,
    kind: str,
    page: int,
    subject_page: int,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if role in {"admin", "editor"}:
        for index, item in enumerate(items, start=1):
            kb.row(
                InlineKeyboardButton(
                    text=f"{texts.BTN_DELETE} {index}",
                    callback_data=DeleteAttachCB(
                        id=item["id"],
                        k=kind,
                        p=page,
                        sp=subject_page,
                    ).pack(),
                )
            )
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_BACK,
            callback_data=BackCB(
                to="card",
                s=0,
                k=kind,
                p=page,
                r=record_id,
                sp=subject_page,
            ).pack(),
        )
    )
    return kb.as_markup()


def extra_files_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=texts.BTN_DONE, callback_data=FilesCB(a="done").pack()))
    kb.row(
        InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=FilesCB(a="cancel").pack())
    )
    return kb.as_markup()


def edit_text_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_CANCEL,
            callback_data=EditFormCB(a="cancel").pack(),
        )
    )
    return kb.as_markup()


def subject_form_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=texts.BTN_CANCEL,
            callback_data=SubjectFormCB(a="cancel").pack(),
        )
    )
    return kb.as_markup()


def confirm_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=texts.BTN_DELETE, callback_data=yes_data))
    kb.row(InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=no_data))
    return kb.as_markup()


async def edit_or_send(bot, chat_id: int, text: str, markup=None, message_id: int | None = None) -> int | None:
    text = texts.clip(text)
    if message_id is not None:
        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup if markup is not None else EMPTY_KEYBOARD,
            )
            return message_id
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return message_id
    try:
        sent = await bot.send_message(chat_id, text, reply_markup=markup)
    except TelegramBadRequest:
        return message_id
    return sent.message_id


async def clear_step_keyboard(bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    message_id = data.get("bot_message_id")
    if not message_id:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=EMPTY_KEYBOARD,
        )
    except TelegramBadRequest:
        return


async def show_wizard_step(bot, chat_id: int, state: FSMContext, text: str, markup, *, move_down: bool) -> None:
    data = await state.get_data()
    current_id = data.get("bot_message_id")
    if move_down:
        if current_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=current_id,
                    reply_markup=EMPTY_KEYBOARD,
                )
            except TelegramBadRequest:
                pass
        sent = await bot.send_message(chat_id, texts.clip(text), reply_markup=markup)
        await state.update_data(bot_message_id=sent.message_id)
        return
    new_id = await edit_or_send(bot, chat_id, text, markup, current_id)
    if new_id and new_id != current_id:
        await state.update_data(bot_message_id=new_id)
