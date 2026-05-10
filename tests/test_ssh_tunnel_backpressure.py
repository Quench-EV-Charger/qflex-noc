"""SSH tunnel reader must close the tunnel if WS send keeps timing out."""
import asyncio

import pytest

from ssh_tunnel import LocalSSHTunnel, SSHTunnelManager


async def test_reader_closes_tunnel_when_ws_send_stalls():
    """If ws_send_callback stalls past the per-call timeout, the reader must give up."""
    mgr = SSHTunnelManager()
    mgr.ws_send_timeout = 0.3  # tighten for test

    class _Reader:
        def __init__(self):
            self._first = True

        async def read(self, _n):
            if self._first:
                self._first = False
                return b"SSH-2.0-Test\r\n"
            await asyncio.sleep(60)
            return b""

    class _Writer:
        def close(self):
            pass

        async def wait_closed(self):
            return None

        def get_extra_info(self, _k):
            return None

    async def stalled_send(_msg):
        await asyncio.sleep(60)  # never returns

    tunnel = LocalSSHTunnel(
        tunnel_id="t1",
        reader=_Reader(),  # type: ignore[arg-type]
        writer=_Writer(),  # type: ignore[arg-type]
    )
    mgr._tunnels["t1"] = tunnel

    task = asyncio.create_task(mgr._ssh_reader_loop("t1", stalled_send))

    # Within ~1s the reader should detect the WS send stall and close the tunnel.
    await asyncio.sleep(1.5)
    assert tunnel.closed, "reader should close tunnel after ws_send timeouts"

    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, BaseException):
        pass
