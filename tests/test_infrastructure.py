import logging
import sys

logger = logging.getLogger('test')


def test_capture(capsys, caplog):
    caplog.set_level(logging.DEBUG)
    print('out')
    print('err', file=sys.stderr)
    magic = 'zzyggdr'
    logger.info(magic)

    streams = capsys.readouterr()
    assert streams.out == 'out\n'
    assert streams.err == 'err\n'
    assert magic in caplog.text


def test_capture_2():
    print('out')
    print('err', file=sys.stderr)
    logger.info('info')
