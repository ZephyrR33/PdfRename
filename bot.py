import os
import tempfile
import logging
from pathlib import Path

import pikepdf
from telegram import Update, Document
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Новые значения
NEW_AUTHOR = os.getenv("NEW_AUTHOR", "Adobe User")
NEW_CREATOR = os.getenv("NEW_CREATOR", "Adobe Acrobat Pro")
NEW_PRODUCER = os.getenv("NEW_PRODUCER", "Adobe PDF Library")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Пришли PDF, и я изменю метаданные:\n"
        f"Автор → {NEW_AUTHOR}\n"
        f"Создатель → {NEW_CREATOR}\n"
        f"Производитель → {NEW_PRODUCER}"
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    doc: Document = msg.document

    if not doc or not doc.file_name:
        await msg.reply_text("Пришли документом PDF файлом.")
        return

    filename = doc.file_name
    is_pdf = (doc.mime_type == "application/pdf") or filename.lower().endswith(".pdf")
    if not is_pdf:
        await msg.reply_text("Это не PDF файл.")
        return

    await msg.chat.send_action(ChatAction.TYPING)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        in_path = td_path / "input.pdf"
        out_path = td_path / "output.pdf"

        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=str(in_path))

        try:
            with pikepdf.open(in_path) as pdf:
                info = pdf.docinfo

                # Меняем классические метаданные
                info["/Author"] = pikepdf.String(NEW_AUTHOR)
                info["/Creator"] = pikepdf.String(NEW_CREATOR)
                info["/Producer"] = pikepdf.String(NEW_PRODUCER)

                # Обновляем XMP если существует
                with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                    meta["dc:creator"] = [NEW_AUTHOR]
                    meta["xmp:CreatorTool"] = NEW_CREATOR
                    meta["pdf:Producer"] = NEW_PRODUCER

                pdf.save(
                    out_path,
                    linearize=False,
                    compress_streams=False,
                    object_stream_mode=pikepdf.ObjectStreamMode.disable,
                )

        except Exception as e:
            logger.exception("Failed to process pdf")
            await msg.reply_text(f"Ошибка обработки PDF: {e}")
            return

        await msg.reply_document(
            document=open(out_path, "rb"),
            filename=filename,
            caption="Готово ✅ Метаданные обновлены"
        )


async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Пришли PDF документом.")


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
    app.add_handler(MessageHandler(filters.ALL, handle_other))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()