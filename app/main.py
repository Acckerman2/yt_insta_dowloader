import asyncio
import sys

import uvicorn

from app.bot import bot, dp
from app.config import settings as cfg
from app.database import db
from app.logger import logger
from app.middlewares import RateLimitMiddleware, ForceSubscribeMiddleware
from app.utils.file_manager import file_manager

from app.handlers import start as start_h, help as help_module, settings as settings_h, stats, broadcast, download, admin


async def on_startup():
    logger.info("Starting bot...")
    await db.connect()
    await file_manager.initialize()

    dp.include_router(start_h.router)
    dp.include_router(help_module.router)
    dp.include_router(download.router)
    dp.include_router(settings_h.router)
    dp.include_router(stats.router)
    dp.include_router(broadcast.router)
    dp.include_router(admin.router)

    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(ForceSubscribeMiddleware())

    if cfg.webhook_url:
        from app.api.webhook import set_webhook
        await set_webhook()
        logger.info(f"Webhook mode: {cfg.webhook_url}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Polling mode")


async def on_shutdown():
    logger.info("Shutting down...")
    if cfg.webhook_url:
        from app.api.webhook import delete_webhook
        await delete_webhook()
    await db.close()
    await bot.session.close()


async def main():
    await on_startup()

    try:
        if cfg.webhook_url:
            from app.api.webhook import app as fastapi_app
            config = uvicorn.Config(
                app=fastapi_app,
                host=cfg.webhook_host,
                port=cfg.webhook_port,
                log_level=cfg.log_level.lower(),
            )
            server = uvicorn.Server(config)
            await server.serve()
        else:
            from fastapi import FastAPI
            health_app = FastAPI()
            @health_app.get("/")
            async def health():
                return {"status": "ok"}
            config = uvicorn.Config(
                health_app,
                host="0.0.0.0",
                port=cfg.webhook_port,
                log_level="error",
            )
            server = uvicorn.Server(config)
            asyncio.create_task(server.serve())
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_as_tasks=True,
            )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
