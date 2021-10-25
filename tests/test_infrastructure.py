import logging
import sys

from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture

logger = logging.getLogger('test')


def test_capture(capsys: CaptureFixture[str], caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    print('out')
    print('err', file=sys.stderr)
    magic = 'zzyggdr'
    logger.info(magic)

    streams = capsys.readouterr()
    assert streams.out == 'out\n'
    assert streams.err == 'err\n'
    assert magic in caplog.text


def test_capture_2() -> None:
    print('out')
    print('err', file=sys.stderr)
    logger.info('info')
