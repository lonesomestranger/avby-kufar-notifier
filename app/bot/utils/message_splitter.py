import asyncio

from aiogram import Bot


async def send_long_message(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode: str | None = None,
    reply_to_message_id: int | None = None,
):
    max_length = 4096
    if len(text) <= max_length:
        await bot.send_message(
            chat_id,
            text,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
        )
        return

    parts = []
    while len(text) > 0:
        if len(text) <= max_length:
            parts.append(text)
            break
        else:
            part = text[:max_length]
            last_newline = part.rfind("\n")
            if last_newline != -1:
                parts.append(part[:last_newline])
                text = text[last_newline + 1 :]
            else:
                last_space = part.rfind(" ")
                if last_space != -1:
                    parts.append(part[:last_space])
                    text = text[last_space + 1 :]
                else:
                    parts.append(part)
                    text = text[max_length:]

    for i, part in enumerate(parts):
        if i == 0 and reply_to_message_id:
            await bot.send_message(
                chat_id,
                part,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id,
            )
        else:
            await bot.send_message(chat_id, part, parse_mode=parse_mode)
        await asyncio.sleep(0.5)
