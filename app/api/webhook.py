from fastapi import FastAPI, Request
from aiogram.types import Update

from app.bot import bot, dp
from app.config import settings
from app.logger import logger

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "running", "bot": "Telegram Media Downloader"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post(f"/webhook/{settings.webhook_secret}")
async def webhook(request: Request):
    try:
        update_data = await request.json()
        update = Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}, 500


async def set_webhook():
    if settings.webhook_url:
        webhook_url = f"{settings.webhook_url}/webhook/{settings.webhook_secret}"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
        )
        logger.info(f"Webhook set to {webhook_url}")


async def delete_webhook():
    await bot.delete_webhook()
    logger.info("Webhook deleted")
