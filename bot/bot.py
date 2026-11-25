from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

ENGINE_URL = os.environ.get("ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
ENGINE_KEY = os.environ.get("ENGINE_KEY", "")


def _client() -> httpx.Client:
    return httpx.Client(timeout=60, headers={"x-api-key": ENGINE_KEY})


def _count(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def format_pending(payload: dict) -> str:
    lines = ["I read this as:"]
    for item in payload["items"]:
        mark = "" if item["status"] == "ok" else " (check this)"
        lines.append(f"- {_count(item['count'])} {item['name']}{mark}")
    if payload["unmatched"]:
        lines.append("Not in the sheet: " + ", ".join(payload["unmatched"]))
    lines.append("Count this meal?")
    return "\n".join(lines)


def format_result(payload: dict) -> str:
    lines = ["So far today:"]
    lows = []
    for row in payload["gaps"]:
        lines.append(f"- {row['label']}: {row['percent']}% of the daily need")
        if row["likely_low"]:
            lows.append(row["label"])
    if lows:
        lines.append("Likely low so far in " + ", ".join(lows) + ".")
    else:
        lines.append("Nothing tracked here is under the average requirement so far today.")
    if payload["suggestions"]:
        lines.append(f"Under ₹{payload['total_price']:g}:")
        for item in payload["suggestions"]:
            reason = f" {item['reason']}" if item.get("reason") else ""
            lines.append(f"- {item['name']} (₹{item['price_inr']:g}).{reason}")
    lines.append(payload["note"])
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    context.user_data["step"] = "sex"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Man", callback_data="sex:man"),
                InlineKeyboardButton("Woman", callback_data="sex:woman"),
            ]
        ]
    )
    await update.message.reply_text("PlatePal. Who is this profile for?", reply_markup=keyboard)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("sex:"):
        context.user_data["sex"] = data.split(":", 1)[1]
        context.user_data["step"] = "diet"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Veg", callback_data="diet:veg"),
                    InlineKeyboardButton("Egg", callback_data="diet:egg"),
                    InlineKeyboardButton("Non-veg", callback_data="diet:nonveg"),
                ]
            ]
        )
        await query.message.reply_text("Diet?", reply_markup=keyboard)
        return
    if data.startswith("diet:"):
        context.user_data["diet"] = data.split(":", 1)[1]
        context.user_data["step"] = "weight"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Skip", callback_data="weight:skip")]])
        await query.message.reply_text("Weight in kg? Or skip and use the reference weight.", reply_markup=keyboard)
        return
    if data == "weight:skip":
        await _save_profile(query.message, context, None)
        return
    if data.startswith("ok:"):
        pending_id = data.split(":", 1)[1]
        user_id = str(update.effective_user.id)
        try:
            with _client() as client:
                response = client.post(
                    f"{ENGINE_URL}/meals/confirm",
                    json={"telegram_user_id": user_id, "pending_id": pending_id},
                )
            if response.status_code >= 400:
                detail = response.json().get("detail", response.text)
                await query.message.reply_text(str(detail))
                return
            await query.message.reply_text(format_result(response.json()))
        except httpx.HTTPError as exc:
            await query.message.reply_text(f"The engine did not answer: {exc}")
        return
    if data.startswith("edit:"):
        await query.message.reply_text("Type the meal again.")


async def _save_profile(message, context, weight_kg: float | None) -> None:
    user_id = str(message.chat.id)
    body = {
        "telegram_user_id": user_id,
        "sex": context.user_data["sex"],
        "diet": context.user_data["diet"],
        "weight_kg": weight_kg,
    }
    try:
        with _client() as client:
            response = client.post(f"{ENGINE_URL}/profile", json=body)
        if response.status_code >= 400:
            await message.reply_text(response.text)
            return
    except httpx.HTTPError as exc:
        await message.reply_text(f"The engine did not answer: {exc}")
        return
    context.user_data["step"] = "ready"
    await message.reply_text("Profile saved. Type a meal, for example: 2 idli and sambar")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    step = context.user_data.get("step")
    text = (update.message.text or "").strip()
    if step == "weight":
        try:
            weight = float(text)
        except ValueError:
            await update.message.reply_text("Send a number in kg, or tap Skip.")
            return
        if not 30 <= weight <= 200:
            await update.message.reply_text("Use a weight between 30 and 200 kg.")
            return
        await _save_profile(update.message, context, weight)
        return
    if step != "ready":
        await update.message.reply_text("Send /start and set a profile first.")
        return
    user_id = str(update.effective_user.id)
    try:
        with _client() as client:
            response = client.post(
                f"{ENGINE_URL}/meals/text",
                json={"telegram_user_id": user_id, "text": text},
            )
    except httpx.HTTPError as exc:
        await update.message.reply_text(f"The engine did not answer: {exc}")
        return
    if response.status_code == 422:
        detail = response.json().get("detail") or {}
        names = detail.get("unmatched") if isinstance(detail, dict) else None
        shown = ", ".join(names) if names else text
        await update.message.reply_text(f"I could not match that to the sheet: {shown}")
        return
    if response.status_code >= 400:
        detail = response.json().get("detail", response.text)
        await update.message.reply_text(str(detail))
        return
    payload = response.json()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes", callback_data=f"ok:{payload['pending_id']}"),
                InlineKeyboardButton("Edit", callback_data=f"edit:{payload['pending_id']}"),
            ]
        ]
    )
    await update.message.reply_text(format_pending(payload), reply_markup=keyboard)


def main() -> None:
    token = os.environ.get("TG_TOKEN")
    if not token:
        raise SystemExit("Set TG_TOKEN in .env")
    if not ENGINE_KEY:
        raise SystemExit("Set ENGINE_KEY in .env")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(on_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    application.run_polling()


if __name__ == "__main__":
    main()
