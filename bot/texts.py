import re
from datetime import datetime

KIND_HW = "dz"
KIND_NOTE = "note"
KIND_ALL = "all"

KIND_LABELS = {
    KIND_HW: "ДЗ",
    KIND_NOTE: "Конспект",
    KIND_ALL: "Все записи",
}

PAGE_SIZE = 10
TOP_LIMIT = 7
MAX_TEXT_LENGTH = 4000
MAX_SUBJECT_NAME = 100
MESSAGE_LIMIT = 4096

CMD_HW = "дз"
CMD_ADD = "добавить"
CMD_SUBJECTS = "предметы"
CMD_ADD_SUBJECT = "добавить_предмет"
CMD_DELETE_SUBJECT = "удалить_предмет"
CMD_EDITOR = "редактор"
CMD_REMOVE_EDITOR = "убрать_редактора"

BTN_HW = "ДЗ"
BTN_NOTE = "Конспект"
BTN_CANCEL = "Отмена"
BTN_TODAY = "Сегодня"
BTN_TOMORROW = "Завтра"
BTN_ENTER_DATE = "Ввести дату"
BTN_DONE = "Готово"
BTN_NO_FILES = "Без вложений"
BTN_PUBLISH = "Опубликовать"
BTN_ABORT = "Отменить"
BTN_BACK = "Назад"
BTN_ALL = "Все записи"
BTN_SHOW_ALL = "Показать все"
BTN_OPEN_FILES = "Открыть вложения"
BTN_ADD_FILES = "Добавить вложения"
BTN_FILES = "Список вложений"
BTN_EDIT_TEXT = "Изменить текст"
BTN_DELETE_RECORD = "Удалить запись"
BTN_DELETE = "Удалить"
BTN_RECORDS = "Записи"
BTN_ADD = "Добавить"
BTN_SUBJECTS = "Предметы"
BTN_ADD_SUBJECT = "Добавить предмет"
BTN_PREV = "Ранее"
BTN_NEXT = "Дальше"

MAIN_MENU = "Главное меню"
KEYBOARD_HINT = "Кнопки внизу."
BTN_HOME = "Главная"
BTN_ABOUT = "ОБ АВТОРЕ"
ABOUT_AUTHOR = """Человек. Легенда. Причина, по которой домашние задания теперь находятся в одном месте.

Александр, 26 лет.
Родом из культурной столицы — Санкт-Петербурга. Ныне обитает в Москве, где продолжает свой нелёгкий путь к мировому господству.

♐️ Знак зодиака: Стрелец.
💼 Род деятельности: гений, миллиардер, филантроп, разработчик, будущий медицинский работник.

🧠 Краткая биография:

С ранних лет проявлял выдающиеся способности к прокрастинации, стратегическому планированию и созданию проектов, которые никто не просил, но все теперь используют.

❤️ Немного о личном:

На данный момент Александр находится в активном поиске спутницы жизни.

Требования к кандидатке:

- Умеет варить борщ (желательно лучше, чем он пишет код).
- Не боится амбициозных мужчин с сомнительными бизнес-идеями.
- Поддерживает разговоры о будущем, технологиях и смысле жизни.
- Готова однажды стать женой человека, у которого на всё есть план, кроме выходных.

🚀 Жизненное кредо:

«Если можно автоматизировать — нужно автоматизировать. Если нельзя — значит, недостаточно постарались».

---

P.S. Если бот вам помог — пользуйтесь на здоровье. Если нашли баг — это не баг, а особенность авторского замысла.

С уважением,
Александр. Ваш покорный создатель, будущий миллиардер и пока ещё холостяк. 🥂"""
PRIVATE = "Бот работает в групповом чате."
NO_ACCESS = "Недостаточно прав."
NO_SUBJECTS = "Предметы пока не добавлены."
NO_RECORDS = "Записей пока нет."
SUBJECT_EXISTS = "Такой предмет уже есть."
SUBJECT_ADDED = "Предмет добавлен."
SUBJECT_DELETED = "Предмет удален."
SUBJECT_NOT_FOUND = "Предмет не найден."
SUBJECT_NAME_REQUIRED = "Укажи название предмета."
SUBJECT_NAME_LONG = "Название слишком длинное."
ASK_SUBJECT_NAME = "Отправь название предмета."
RECORD_ADDED = "Запись добавлена."
RECORD_DELETED = "Запись удалена."
RECORD_NOT_FOUND = "Запись не найдена."
TEXT_TOO_LONG = "Текст слишком длинный. Максимум 4000 символов."
DATE_FORMAT = "Отправь дату в формате ДД.ММ.ГГГГ."
ASK_TEXT = "Отправь текст. Если текста нет, отправь 'нет'."
ASK_NEW_TEXT = "Отправь новый текст. Чтобы очистить, отправь 'нет'."
ASK_FILES = "Отправь фото, файлы или несколько сообщений подряд. Когда закончишь, нажми 'Готово'."
ASK_MORE_FILES = "Отправь фото или файлы. Можно несколько сообщений подряд. Когда закончишь, нажми 'Готово'."
FILES_ADDED = "Вложения добавлены."
SEND_FILE = "Отправь фото или файл."
NEED_FILE = "Сначала отправь фото или файл."
SEND_FAILED = "Не удалось отправить вложения."
NO_ATTACHMENTS = "Вложений нет."
STALE = "Кнопка устарела."
CANCELLED = "Отменено."
USER_NOT_FOUND = "Пользователь не найден."
IS_ADMIN = "Это администратор."
EDITOR_SET = "Назначен редактором."
EDITOR_REMOVED = "Роль редактора снята."
NOT_EDITOR = "Этот пользователь не редактор."
SPECIFY_EDITOR = "Укажи пользователя: /редактор @username"
SPECIFY_REMOVE_EDITOR = "Укажи пользователя: /убрать_редактора @username"
SAVE_FAILED = "Не удалось сохранить запись."
PREVIEW_WAIT = "Нажми «Опубликовать» или «Отменить»."
CHOOSE_SUBJECT = "Выбери предмет:"
CHOOSE_KIND = "Выбери тип:"
CHOOSE_DATE = "Выбери дату:"
CHOOSE_BUTTON = "Выбери кнопку."
ATTACHMENT_NOT_FOUND = "Вложение не найдено."

_DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def clip(text: str, limit: int = MESSAGE_LIMIT) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def page_count(total: int, size: int = PAGE_SIZE) -> int:
    if total <= 0:
        return 1
    return (total + size - 1) // size


def clamp_page(page: int, pages: int) -> int:
    if pages < 1:
        return 0
    if page < 0:
        return 0
    if page >= pages:
        return pages - 1
    return page


def with_page(text: str, page: int, pages: int) -> str:
    if pages <= 1:
        return text
    return f"{text}\nСтр. {page + 1} из {pages}"


def button_label(name: str, limit: int = 64) -> str:
    compact = " ".join(name.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def format_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return value
    return parsed.strftime("%d.%m.%Y")


def parse_user_date(value: str) -> str | None:
    raw = value.strip()
    if _DATE_RE.fullmatch(raw) is None:
        return None
    try:
        parsed = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        return None
    return parsed.isoformat()


def is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def check_subject_name(raw: str) -> tuple[str, str]:
    name = " ".join(raw.split())
    if not name:
        return "empty", ""
    if len(name) > MAX_SUBJECT_NAME:
        return "long", ""
    return "ok", name


def normalize_text(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if not value:
        return "empty", ""
    if value.casefold() == "нет":
        return "ok", ""
    if len(value) > MAX_TEXT_LENGTH:
        return "long", ""
    return "ok", value


def plural(count: int, one: str, few: str, many: str) -> str:
    number = abs(count) % 100
    digit = number % 10
    if 11 <= number <= 14:
        word = many
    elif digit == 1:
        word = one
    elif 2 <= digit <= 4:
        word = few
    else:
        word = many
    return f"{count} {word}"


def attachments_summary(photos: int, documents: int) -> str:
    parts: list[str] = []
    if photos:
        parts.append(f"{photos} фото")
    if documents:
        parts.append(plural(documents, "файл", "файла", "файлов"))
    if not parts:
        return "нет"
    return ", ".join(parts)


def author_label(username: str | None, telegram_id: int | None) -> str:
    if username:
        return f"@{username}"
    if telegram_id:
        return str(telegram_id)
    return "неизвестно"


def attachment_header(subject: str, date_iso: str) -> str:
    return f"{subject}\n{format_date(date_iso)}"


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind)


def choose_kind_text() -> str:
    return f"Новая запись\n{CHOOSE_KIND}"


def choose_subject_text(page: int, pages: int, *, wizard: bool) -> str:
    base = f"Новая запись\n{CHOOSE_SUBJECT}" if wizard else CHOOSE_SUBJECT
    return with_page(base, page, pages)


def choose_date_text(subject: str) -> str:
    return f"{subject}\n{CHOOSE_DATE}"


def ask_text_screen(subject: str, kind: str, date_iso: str) -> str:
    return f"{subject}. {kind_label(kind)}. {format_date(date_iso)}\n{ASK_TEXT}"


def ask_files_screen(subject: str, kind: str, date_iso: str) -> str:
    return f"{subject}. {kind_label(kind)}. {format_date(date_iso)}\n{ASK_FILES}"


def ask_more_files_screen(subject: str, kind: str, date_iso: str) -> str:
    return f"{subject}. {kind_label(kind)}. {format_date(date_iso)}\n{ASK_MORE_FILES}"


def sections_text(subject: str) -> str:
    return f"{subject}. Выбери раздел:"


def records_text(subject: str, kind: str, *, empty: bool, page: int = 0, pages: int = 1) -> str:
    title = f"{subject}. {kind_label(kind)}."
    if empty:
        return f"{title}\n{NO_RECORDS}"
    return with_page(title, page, pages)


def confirm_delete_subject(name: str) -> str:
    return f"Удалить предмет «{name}» вместе со всеми его записями?"


def confirm_delete_record(kind: str, subject: str, date_iso: str) -> str:
    return f"Удалить {kind_label(kind)} по {subject} за {format_date(date_iso)}?"


def confirm_delete_attachment(index: int, total: int) -> str:
    return f"Удалить вложение {index} из {total}?"


def subjects_message(names: list[str]) -> str:
    if not names:
        return NO_SUBJECTS
    lines = ["Предметы:"]
    for index, name in enumerate(names, start=1):
        lines.append(f"{index}. {name}")
        if len("\n".join(lines)) > MESSAGE_LIMIT - 20:
            lines[-1] = "..."
            break
    return clip("\n".join(lines))


def record_button_text(date_iso: str, text: str, kind: str | None = None) -> str:
    date = format_date(date_iso)
    short = " ".join((text or "").split())
    if len(short) > 30:
        short = short[:30]
    if kind in {KIND_HW, KIND_NOTE}:
        label = kind_label(kind)
        result = f"{date}. {label}. {short}" if short else f"{date}. {label}"
    elif short:
        result = f"{date}. {short}"
    else:
        result = date
    if len(result) > 64:
        return result[:64]
    return result


def _fit_body(head: list[str], body: str, footer: list[str], *, empty_body: bool) -> str:
    def assemble(value: str) -> str:
        if empty_body or not value:
            parts = head + [""] + footer
        else:
            parts = head + ["", value, ""] + footer
        return "\n".join(parts)

    result = assemble(body)
    if len(result) <= MESSAGE_LIMIT:
        return result
    if not body:
        return clip(result)
    extra = len(result) - MESSAGE_LIMIT
    keep = max(0, len(body) - extra - 3)
    trimmed = body[:keep] + "..."
    fitted = assemble(trimmed)
    if len(fitted) <= MESSAGE_LIMIT:
        return fitted
    return clip(fitted)


def card_text(
    *,
    subject: str,
    kind: str,
    date_iso: str,
    body: str,
    username: str | None,
    telegram_id: int | None,
    photos: int,
    documents: int,
) -> str:
    head = [subject, kind_label(kind), format_date(date_iso)]
    footer = [
        f"Добавил: {author_label(username, telegram_id)}",
        f"Вложения: {attachments_summary(photos, documents)}",
    ]
    return _fit_body(head, body, footer, empty_body=not body)


def preview_text(
    *,
    subject: str,
    kind: str,
    date_iso: str,
    body: str,
    photos: int,
    documents: int,
) -> str:
    shown = body if body else "нет"
    lines = [
        f"Предмет: {subject}",
        f"Тип: {kind_label(kind)}",
        f"Дата: {format_date(date_iso)}",
        "Текст:",
        shown,
        f"Вложения: {attachments_summary(photos, documents)}",
    ]
    result = "\n".join(lines)
    if len(result) <= MESSAGE_LIMIT:
        return result
    extra = len(result) - MESSAGE_LIMIT
    keep = max(0, len(shown) - extra - 3)
    lines[4] = shown[:keep] + "..."
    return clip("\n".join(lines))


def attachment_title(file_type: str, file_name: str | None) -> str:
    if file_type == "photo":
        return "фото.jpg"
    name = " ".join((file_name or "").split())
    if not name:
        return "файл"
    if len(name) > 40:
        return name[:37] + "..."
    return name


def attachment_list_text(items: list) -> str:
    if not items:
        return NO_ATTACHMENTS
    lines = ["Вложения:", ""]
    for index, item in enumerate(items, start=1):
        lines.append(
            f"{index}. {attachment_title(item['file_type'], item['file_name'])}"
        )
    return clip("\n".join(lines))
