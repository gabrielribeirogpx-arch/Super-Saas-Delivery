from app.routers.webhook import _coerce_to_bool, _get_print_settings


class _FakeQuery:
    def __init__(self, tenant):
        self._tenant = tenant

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._tenant


class _FakeDB:
    def __init__(self, tenant):
        self._tenant = tenant

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._tenant)


class _Tenant:
    def __init__(self, auto_print=None, printer_name=None):
        self.auto_print = auto_print
        self.printer_name = printer_name


def test_coerce_to_bool_accepts_common_false_strings():
    for value in ["0", "false", "FALSE", "off", "no", "n", ""]:
        assert _coerce_to_bool(value, default=True) is False


def test_get_print_settings_preserves_false_string_in_database(monkeypatch):
    monkeypatch.setenv("AUTO_PRINT", "1")
    monkeypatch.setenv("PRINTER_NAME", "ENV_PRINTER")

    auto_print, printer = _get_print_settings(
        tenant_id=1,
        db=_FakeDB(_Tenant(auto_print="false", printer_name="DB_PRINTER")),
    )

    assert auto_print is False
    assert printer == "DB_PRINTER"


def test_get_print_settings_uses_env_when_database_is_none(monkeypatch):
    monkeypatch.setenv("AUTO_PRINT", "true")
    monkeypatch.setenv("PRINTER_NAME", "ENV_PRINTER")

    auto_print, printer = _get_print_settings(
        tenant_id=1,
        db=_FakeDB(_Tenant(auto_print=None, printer_name=None)),
    )

    assert auto_print is True
    assert printer == "ENV_PRINTER"
