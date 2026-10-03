import asyncio

import pytest

from strategy_engine import await_with_timeout


def test_completed_operation_returns_before_deadline():
    async def complete_immediately():
        return "finished"

    result = asyncio.run(await_with_timeout(complete_immediately(), 0.5))
    assert result == "finished"


def test_stalled_operation_is_cancelled_at_deadline():
    async def stall():
        await asyncio.sleep(0.2)

    with pytest.raises(TimeoutError):
        asyncio.run(await_with_timeout(stall(), 0.01))
