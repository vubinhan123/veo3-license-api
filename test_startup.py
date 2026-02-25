import asyncio
from app.main import app

async def test():
    try:
        async with app.router.lifespan_context(app) as state:
            print("lifespan success!")
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(test())
