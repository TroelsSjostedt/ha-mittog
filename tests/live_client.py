"""Manual live check: connect to a station for N seconds and print changed boards."""
import asyncio, logging, pathlib, sys, time as _t
import types; _p = types.ModuleType("mittog"); _p.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "mittog")]; sys.modules.setdefault("mittog", _p)
import aiohttp
from mittog.client import MitTogClient
from mittog.model import train_summary

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

async def main(station, seconds):
    t0 = _t.time()
    def on_board(board):
        print(f"+{_t.time()-t0:5.1f}s board {board.station}: {len(board.trains)} trains")
        for tr in board.upcoming()[:3]:
            print("   ", train_summary(tr))
    def on_status(v):
        print(f"+{_t.time()-t0:5.1f}s status connected={v}")
    async with aiohttp.ClientSession() as session:
        c = MitTogClient(session, station, on_board, on_status)
        b = await c.fetch_once()
        print("fetch_once ->", len(b.trains), "trains")
        c.start()
        await asyncio.sleep(seconds)
        await c.stop()
        print("stopped cleanly")

asyncio.run(main(sys.argv[1], int(sys.argv[2])))
