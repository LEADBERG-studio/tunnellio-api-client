from tunnellio.cli import build_parser


def test_plan_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['plan'])
    assert args.command == 'plan'
    assert args.output == 'json'
    assert args.local_port == 3000
    assert args.verbose is False


def test_connect_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['connect'])
    assert args.command == 'connect'
    assert args.output == 'text'
    assert args.run is False
    assert args.local_port == 3000


def test_meta_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['meta'])
    assert args.command == 'meta'
    assert args.output == 'json'


def test_verbose_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(['--verbose', 'meta'])
    assert args.verbose is True
