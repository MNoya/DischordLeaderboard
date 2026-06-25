from bot.services.pod_format_select import WRITE_IN_VALUE, format_options
from bot.sets import active_set_code


def test_write_in_launcher_is_always_offered():
    values = [option.value for option in format_options(None)]

    assert WRITE_IN_VALUE in values


def test_active_set_is_default_when_no_current_code():
    defaulted = [option.value for option in format_options(None) if option.default]

    assert defaulted == [active_set_code()]


def test_written_in_code_surfaces_as_the_selected_option():
    options = format_options("ZZZ")

    selected = [option.value for option in options if option.default]
    assert selected == ["ZZZ"]
