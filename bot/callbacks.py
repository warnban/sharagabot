from aiogram.filters.callback_data import CallbackData
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery


class MenuCB(CallbackData, prefix="menu"):
    a: str


class SubjectCB(CallbackData, prefix="subject"):
    id: int
    p: int


class PickCB(CallbackData, prefix="pick"):
    id: int


class SectionCB(CallbackData, prefix="section"):
    subject_id: int
    kind: str
    sp: int


class RecordCB(CallbackData, prefix="record"):
    id: int
    k: str
    p: int
    sp: int


class PageCB(CallbackData, prefix="page"):
    # c: sub (list), add (new record), rec (records)
    # p: page, -1 is not used here
    # s: subject id for records
    # k: dz, note, all
    # sp: subject list page
    p: int
    c: str
    s: int
    k: str
    sp: int


class BackCB(CallbackData, prefix="back"):
    # to=sub: p is the subject list page
    # to=sec: s is subject id, sp is the subject list page
    # to=rec: s is subject id, k is section, p is record page (-1 = last 7)
    # to=card: r is record id, k/p/sp keep the list context
    to: str
    s: int
    k: str
    p: int
    r: int
    sp: int


class FlowCB(CallbackData, prefix="w"):
    a: str


class OpenAttachCB(CallbackData, prefix="attach"):
    record_id: int


class ListAttachCB(CallbackData, prefix="attachments"):
    record_id: int
    k: str
    p: int
    sp: int


class DeleteAttachCB(CallbackData, prefix="delete_attachment"):
    id: int
    k: str
    p: int
    sp: int


class AddFilesCB(CallbackData, prefix="addatt"):
    id: int
    k: str
    p: int
    sp: int


class EditCB(CallbackData, prefix="edit"):
    id: int
    k: str
    p: int
    sp: int


class DelRecCB(CallbackData, prefix="delrec"):
    id: int
    k: str
    p: int
    sp: int


class FilesCB(CallbackData, prefix="files"):
    a: str


class SubjectFormCB(CallbackData, prefix="subform"):
    a: str


class EditFormCB(CallbackData, prefix="edform"):
    a: str


class ConfirmSubjectCB(CallbackData, prefix="cfsub"):
    id: int
    y: int


class ConfirmRecordCB(CallbackData, prefix="cfrec"):
    id: int
    y: int
    k: str
    p: int
    sp: int


class ConfirmAttachCB(CallbackData, prefix="cfatt"):
    id: int
    y: int
    k: str
    p: int
    sp: int


def has_member(internal_chat_id: int | None, db_user: object) -> bool:
    return internal_chat_id is not None and db_user is not None


async def answer_callback(callback: CallbackQuery, text: str | None = None) -> None:
    try:
        if text:
            await callback.answer(text)
        else:
            await callback.answer()
    except TelegramBadRequest:
        return
