"""Tests avec des réponses API-Football simulées : python3 -m unittest discover tests"""
import json
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
import apifootball as api  # noqa: E402
import availability  # noqa: E402
import model  # noqa: E402

PSG, LEH = 85, 1001


def player(pid, name, team, pos, minutes, goals, assists):
    return {"player": {"id": pid, "name": name},
            "statistics": [{"team": {"id": team}, "games": {"position": pos, "minutes": minutes},
                            "goals": {"total": goals, "assists": assists}}]}


KICKOFF = (datetime.now(timezone.utc) + timedelta(minutes=45)).replace(microsecond=0)
FIXTURES = [{"fixture": {"id": 555, "date": KICKOFF.isoformat()},
             "teams": {"home": {"id": LEH, "name": "Le Havre"}, "away": {"id": PSG, "name": "Paris Saint Germain"}}},
            {"fixture": {"id": 556, "date": KICKOFF.isoformat()},
             "teams": {"home": {"id": 7, "name": "Lens"}, "away": {"id": 8, "name": "Lille"}}}]
PLAYERS = [player(1, "Buteur", PSG, "Attacker", 900, 9, 2), player(2, "Ailier", PSG, "Attacker", 800, 3, 4),
           player(3, "Gardien", PSG, "Goalkeeper", 900, 0, 0), player(4, "Défenseur", PSG, "Defender", 880, 0, 1),
           player(5, "Remplaçant", PSG, "Midfielder", 120, 0, 0),
           player(10, "Attaquant", LEH, "Attacker", 900, 4, 1), player(11, "Gardien LH", LEH, "Goalkeeper", 900, 0, 0)]
INJURIES = [{"player": {"id": 1, "name": "Buteur", "type": "Missing Fixture", "reason": "Ischio-jambiers"},
             "team": {"id": PSG}, "fixture": {"id": 555}},
            {"player": {"id": 4, "name": "Défenseur", "type": "Questionable", "reason": "Cheville"},
             "team": {"id": PSG}, "fixture": {"id": 555}},
            {"player": {"id": 99, "name": "Autre match", "type": "Missing Fixture", "reason": "x"},
             "team": {"id": PSG}, "fixture": {"id": 444}}]
LINEUPS = [{"team": {"id": PSG}, "startXI": [{"player": {"id": i}} for i in (2, 3, 5)]},
           {"team": {"id": LEH}, "startXI": [{"player": {"id": i}} for i in (10, 11)]}]


def fake_call(lineups):
    def call(endpoint, params, ttl):
        resp = {"fixtures": FIXTURES, "injuries": INJURIES, "players": PLAYERS,
                "fixtures/lineups": lineups}[endpoint]
        return {"response": resp, "paging": {"current": 1, "total": 1}, "errors": []}
    return call


class Matching(unittest.TestCase):
    def test_noms_differents(self):
        day = KICKOFF.date().isoformat()
        self.assertEqual(availability.match_fixture(FIXTURES, day, "Le Havre", "Paris SG")["fixture"]["id"], 555)
        self.assertEqual(availability.match_fixture(FIXTURES, day, "Lens", "Lille")["fixture"]["id"], 556)
        self.assertIsNone(availability.match_fixture(FIXTURES, day, "Marseille", "Nice"))


class Absences(unittest.TestCase):
    def test_blesses_sans_composition(self):
        w = availability.importance(PLAYERS, PSG)
        ab, lineup = availability.absences(555, PSG, INJURIES, [], w)
        self.assertFalse(lineup)
        self.assertEqual([a["name"] for a in ab], ["Buteur", "Défenseur"])
        self.assertEqual(ab[1]["weight"], 0.5)          # incertain = demi-poids
        self.assertAlmostEqual(ab[0]["att_share"], 10.4 / 16.9, places=3)

    def test_composition_officielle(self):
        w = availability.importance(PLAYERS, PSG)
        ab, lineup = availability.absences(555, PSG, INJURIES, LINEUPS, w)
        self.assertTrue(lineup)
        # Le défenseur incertain n'est pas titulaire : absent confirmé, poids plein.
        self.assertEqual({a["name"]: a["weight"] for a in ab}, {"Buteur": 1.0, "Défenseur": 1.0})

    def test_multiplicateurs(self):
        w = availability.importance(PLAYERS, PSG)
        ab, _ = availability.absences(555, PSG, INJURIES, [], w)
        lam, mu = availability.multipliers([], ab)        # PSG à l'extérieur
        self.assertGreater(lam, 1.0)                       # Le Havre marque plus facilement
        self.assertLess(mu, 1.0)                           # le PSG marque moins
        self.assertGreaterEqual(mu, 1 - availability.MAX_ATT_LOSS)
        self.assertEqual(availability.multipliers([], []), (1.0, 1.0))


class ForLeague(unittest.TestCase):
    def test_bout_en_bout(self):
        day = KICKOFF.date().isoformat()
        with mock.patch.object(api, "call", fake_call(LINEUPS)):
            out = availability.for_league("F1", [(day, "Le Havre", "Paris SG")], 2026)
        info = out[(day, "Le Havre", "Paris SG")]
        self.assertEqual(info["fixture"], 555)
        self.assertTrue(info["lineups"] and info["weighted"])
        self.assertLess(info["mu_mult"], 1.0)

    def test_effet_sur_les_probabilites(self):
        fit = model.Fit(["A", "B"], [0.0, 0.0], [0.0, 0.0], 0.25, -0.05)
        base = model.markets(fit.score_matrix("A", "B"))
        adj = model.markets(fit.score_matrix("A", "B", 1.0, 0.75))
        self.assertGreater(adj["home"], base["home"])


class Budget(unittest.TestCase):
    def test_quota(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(api, "CACHE", pathlib.Path(d)), \
                mock.patch.object(api, "DAILY_BUDGET", 2):
            api._spend(); api._spend()
            with self.assertRaises(api.BudgetExceeded):
                api._spend()

    def test_cache(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(api, "CACHE", pathlib.Path(d)), \
                mock.patch.dict("os.environ", {"API_FOOTBALL_KEY": "test"}), \
                mock.patch("urllib.request.urlopen") as op:
            op.return_value.__enter__.return_value.read.return_value = json.dumps(
                {"response": [1], "errors": []}).encode()
            self.assertEqual(api.get("injuries", {"league": 61, "season": 2026}, 3600), [1])
            self.assertEqual(api.get("injuries", {"league": 61, "season": 2026}, 3600), [1])
            self.assertEqual(op.call_count, 1)           # 2e appel servi par le cache
            self.assertEqual(op.call_args[0][0].headers["X-apisports-key"], "test")


if __name__ == "__main__":
    unittest.main()
