from bot.slug import disambiguate_slug, slugify


class TestSlugify:
    def test_simple_name(self):
        assert slugify("nlaframboise") == "nlaframboise"

    def test_uppercase_lowercased(self):
        assert slugify("Elfandor") == "elfandor"

    def test_parenthetical_collapsed(self):
        assert slugify("Neo (Marc)") == "neo-marc"
        assert slugify("Luke (lukkentopia)") == "luke-lukkentopia"

    def test_spaces_become_dash(self):
        assert slugify("Mike Provencher") == "mike-provencher"

    def test_alphanumeric_kept(self):
        assert slugify("HAS510") == "has510"
        assert slugify("Tim17") == "tim17"

    def test_runs_collapse(self):
        assert slugify("a___b...c") == "a-b-c"

    def test_leading_trailing_trim(self):
        assert slugify("__foo__") == "foo"

    def test_empty_falls_back_to_player_id(self):
        assert slugify("", "abc12345-rest") == "player-abc12345"
        assert slugify("🔥🔥🔥", "abc12345") == "player-abc12345"

    def test_empty_with_no_id_uses_x(self):
        assert slugify("") == "player-x"


class TestDisambiguate:
    def test_no_collision(self):
        assert disambiguate_slug("foo", []) == "foo"
        assert disambiguate_slug("foo", ["bar", "baz"]) == "foo"

    def test_first_collision(self):
        assert disambiguate_slug("foo", ["foo"]) == "foo-2"

    def test_chain_collisions(self):
        assert disambiguate_slug("foo", ["foo", "foo-2"]) == "foo-3"
        assert disambiguate_slug("foo", ["foo", "foo-2", "foo-3"]) == "foo-4"

    def test_iterable_input(self):
        # accepts any iterable, not just list
        assert disambiguate_slug("foo", iter(["foo"])) == "foo-2"
